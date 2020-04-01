"""
This module defines a SecureSocket class that wraps the normal socket by adding
TLS-like functionality of providing data integrity, confidentiality and
authenticity. The reason why we're not using TLS is because the Python
implementation enforces the use of certificates and we want to also allow
password based authentication. This implements the common class, and the Slave
and Controller implement their sides of the handshake algorithms.

Copyright 2016 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import pickle
import hashlib
import hmac
from lnst.Common.Utils import not_imported
from lnst.Common.LnstError import LnstError

DH_GROUP = {"p": int("0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"\
                     "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"\
                     "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"\
                     "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"\
                     "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"\
                     "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"\
                     "83655D23DCA3AD961C62F356208552BB9ED529077096966D"\
                     "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"\
                     "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"\
                     "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"\
                     "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16),
            "g": 2}

# to support both Python2.6 and 2.7, use following workaround to count
# the bit length of a number; note that the workaround does not work for
# value 0 but we don't use it for such value
def bit_length(i):
    try:
        return i.bit_length()
    except AttributeError:
        return len(bin(i)) - 2

DH_GROUP["q"] = (DH_GROUP["p"]-1)//2
DH_GROUP["q_size"] = bit_length(DH_GROUP["q"])//8
if bit_length(DH_GROUP["q"])%8:
    DH_GROUP["q_size"] += 1
DH_GROUP["p_size"] = bit_length(DH_GROUP["p"])//8
if bit_length(DH_GROUP["p"])%8:
    DH_GROUP["p_size"] += 1

SRP_GROUP = {"p": int("0xAC6BDB41324A9A9BF166DE5E1389582FAF72B6651987EE07FC"
                      "3192943DB56050A37329CBB4A099ED8193E0757767A13DD52312"
                      "AB4B03310DCD7F48A9DA04FD50E8083969EDB767B0CF6095179A"
                      "163AB3661A05FBD5FAAAE82918A9962F0B93B855F97993EC975E"
                      "EAA80D740ADBF4FF747359D041D5C33EA71D281E446B14773BCA"
                      "97B43A23FB801676BD207A436C6481F1D2B9078717461A5B9D32"
                      "E688F87748544523B524B0D57D5EA77A2775D2ECFA032CFBDBF5"
                      "2FB3786160279004E57AE6AF874E7303CE53299CCC041C7BC308"
                      "D82A5698F3A8D0C38271AE35F8E9DBFBB694B5C803D89F7AE435"
                      "DE236D525F54759B65E372FCD68EF20FA7111F9E4AFF73", 16),
             "g": 2}

SRP_GROUP["q"] = (SRP_GROUP["p"]-1)//2
SRP_GROUP["q_size"] = bit_length(SRP_GROUP["q"])//8
if bit_length(SRP_GROUP["q"])%8:
    SRP_GROUP["q_size"] += 1
SRP_GROUP["p_size"] = bit_length(SRP_GROUP["p"])//8
if bit_length(SRP_GROUP["p"])%8:
    SRP_GROUP["p_size"] += 1

class SecSocketException(LnstError):
    pass

cryptography = not_imported
hashes = not_imported
Cipher = not_imported
algorithms = not_imported
modes = not_imported
padding = not_imported
ec = not_imported
EllipticCurvePrivateKey = not_imported
EllipticCurvePublicKey = not_imported
RSAPrivateKey = not_imported
RSAPublicKey = not_imported
DSAPrivateKey = not_imported
DSAPublicKey = not_imported
default_backend = not_imported
cryptography_imported = not_imported
def cryptography_imports():
    global cryptography_imported
    if cryptography_imported:
        return

    global cryptography
    global hashes
    global Cipher
    global algorithms
    global modes
    global padding
    global ec
    global EllipticCurvePrivateKey
    global EllipticCurvePublicKey
    global RSAPrivateKey
    global RSAPublicKey
    global DSAPrivateKey
    global DSAPublicKey
    global default_backend

    try:
        import cryptography.exceptions
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.asymmetric import padding, ec
        from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
        from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
        from cryptography.hazmat.primitives.asymmetric.dsa import DSAPrivateKey
        from cryptography.hazmat.primitives.asymmetric.dsa import DSAPublicKey
        from cryptography.hazmat.backends import default_backend
        cryptography_imported = True
    except ImportError:
        raise SecSocketException("Library 'cryptography' missing "\
                                 "can't establish secure channel.")

class SecureSocket(object):
    def __init__(self, soc):
        self._role = None
        self._socket = soc

        self._master_secret = ""

        self._ctl_random = None
        self._slave_random = None

        self._current_write_spec = {"enc_key": None,
                                    "mac_key": None,
                                    "seq_num": 0}
        self._current_read_spec = {"enc_key": None,
                                   "mac_key": None,
                                   "seq_num": 0}
        self._next_write_spec = {"enc_key": None,
                                 "mac_key": None,
                                 "seq_num": 0}
        self._next_read_spec = {"enc_key": None,
                                "mac_key": None,
                                "seq_num": 0}

    def send_msg(self, msg):
        pickled_msg = pickle.dumps(msg)
        return self.send(pickled_msg)

    def recv_msg(self):
        pickled_msg = self.recv()
        if pickled_msg == b"":
            raise SecSocketException("Disconnected")
        msg = pickle.loads(pickled_msg)
        return msg

    def _add_mac_sign(self, data):
        if not self._current_write_spec["mac_key"]:
            return data
        cryptography_imports()

        msg = (bytes(str(self._current_write_spec["seq_num"]).encode('ascii'))
               + bytes(str(len(data)).encode('ascii'))
               + data)
        signature = hmac.new(self._current_write_spec["mac_key"],
                             msg,
                             hashlib.sha256)
        signed_msg = {"data": data,
                      "signature": signature.digest()}
        return pickle.dumps(signed_msg)

    def _del_mac_sign(self, signed_data):
        if not self._current_read_spec["mac_key"]:
            return signed_data
        cryptography_imports()

        signed_msg = pickle.loads(signed_data)
        data = signed_msg["data"]
        msg = (bytes(str(self._current_read_spec["seq_num"]).encode('ascii'))
               + bytes(str(len(data)).encode('ascii'))
               + data)

        signature = hmac.new(self._current_read_spec["mac_key"],
                             msg,
                             hashlib.sha256)

        if signature.digest() != signed_msg["signature"]:
            return None
        return data

    def _add_padding(self, data):
        if not self._current_write_spec["enc_key"]:
            return data
        cryptography_imports()

        block_size = algorithms.AES.block_size//8
        pad_length = block_size - (len(data) % block_size)
        pad_char = bytes([pad_length])
        padding = pad_length * pad_char

        padded_data = data+padding
        return padded_data

    def _del_padding(self, data):
        if not self._current_read_spec["enc_key"]:
            return data
        cryptography_imports()

        pad_length = ord(data[-1])
        for char in data[-pad_length]:
            if ord(char) != pad_length:
                return None

        return data[:-pad_length]

    def _add_encrypt(self, data):
        if not self._current_write_spec["enc_key"]:
            return data
        cryptography_imports()

        iv = os.urandom(algorithms.AES.block_size//8)
        mode = modes.CBC(iv)
        key = self._current_write_spec["enc_key"]
        cipher = Cipher(algorithms.AES(key), mode, default_backend())
        encryptor = cipher.encryptor()

        encrypted_data = encryptor.update(data) + encryptor.finalize()

        encrypted_msg = {"iv": iv,
                         "enc_data": encrypted_data}

        return pickle.dumps(encrypted_msg)

    def _del_encrypt(self, data):
        if not self._current_read_spec["enc_key"]:
            return data
        cryptography_imports()

        encrypted_msg = pickle.loads(data)
        encrypted_data = encrypted_msg["enc_data"]

        iv = encrypted_msg["iv"]
        mode = modes.CBC(iv)
        key = self._current_read_spec["enc_key"]
        cipher = Cipher(algorithms.AES(key), mode, default_backend())
        decryptor = cipher.decryptor()

        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        return decrypted_data

    def _protect_data(self, data):
        signed = self._add_mac_sign(data)
        padded = self._add_padding(signed)
        encrypted = self._add_encrypt(padded)

        self._current_write_spec["seq_num"] += 1
        return encrypted

    def _uprotect_data(self, encrypted):
        padded = self._del_encrypt(encrypted)
        signed = self._del_padding(padded)

        if signed is None:
            #preventing timing attacks
            self._del_mac_sign(padded)
            return None

        data = self._del_mac_sign(signed)

        self._current_read_spec["seq_num"] += 1
        return data

    def send(self, data):
        protected_data = self._protect_data(data)

        transmit_data = bytes(str(len(protected_data)).encode('ascii')) + b" " + protected_data

        return self._socket.sendall(transmit_data)

    def recv(self):
        length = b""
        while True:
            c = self._socket.recv(1)

            if c == b' ':
                length = int(length.decode('ascii'))
                break
            elif c == b"":
                return b""
            else:
                length += c

        data = b""
        while len(data) < length:
            c = self._socket.recv(length - len(data))
            if c == b"":
                return b""
            else:
                data += c

        msg = self._uprotect_data(data)
        if msg is None:
            return self.recv()
        return self._handle_internal(msg)

    def _handle_internal(self, orig_msg):
        try:
            msg = pickle.loads(orig_msg)
        except:
            return orig_msg
        if "type" in msg and msg["type"] == "change_cipher_spec":
            self._change_read_cipher_spec()
            return self.recv()
        else:
            return orig_msg

    def _send_change_cipher_spec(self):
        change_cipher_spec_msg = {"type": "change_cipher_spec"}
        self.send_msg(change_cipher_spec_msg)
        self._change_write_cipher_spec()
        return

    def fileno(self):
        """needed to work with select()"""
        return self._socket.fileno()

    def close(self):
        return self._socket.close()

    @property
    def closed(self):
        return self._socket.fileno == -1

    def shutdown(self, how):
        return self._socket.shutdown(how)

    def _change_read_cipher_spec(self):
        self._current_read_spec = self._next_read_spec
        self._next_read_spec = {"enc_key": None,
                                "mac_key": None,
                                "seq_num": 0}
        return

    def _change_write_cipher_spec(self):
        self._current_write_spec = self._next_write_spec
        self._next_write_spec = {"enc_key": None,
                                 "mac_key": None,
                                 "seq_num": 0}
        return

    def p_SHA256(self, secret, seed, length):
        prev_a = seed
        result = b""
        while len(result) < length:
            a = hmac.new(secret, msg=prev_a, digestmod=hashlib.sha256)
            prev_a = a.digest()
            hmac_hash = hmac.new(secret,
                                 msg=a.digest()+seed,
                                 digestmod=hashlib.sha256)
            result += hmac_hash.digest()
        return result[:length]

    def PRF(self, secret, label, seed, length):
        return self.p_SHA256(secret, label+seed, length)

    def _init_cipher_spec(self):
        if self._role == "server":
            client_spec = self._next_read_spec
            server_spec = self._next_write_spec
        elif self._role == "client":
            client_spec = self._next_write_spec
            server_spec = self._next_read_spec
        else:
            raise SecSocketException("Socket without a role!")
        cryptography_imports()

        aes_keysize = max(algorithms.AES.key_sizes)//8
        mac_keysize = hashlib.sha256().block_size

        prf_seq = self.PRF(self._master_secret,
                           "key expansion",
                           self._slave_random + self._ctl_random,
                           2*aes_keysize + 2*mac_keysize)

        client_spec["enc_key"] = prf_seq[:aes_keysize]
        prf_seq = prf_seq[aes_keysize:]
        server_spec["enc_key"] = prf_seq[:aes_keysize]
        prf_seq = prf_seq[aes_keysize:]

        client_spec["mac_key"] = prf_seq[:mac_keysize]
        prf_seq = prf_seq[mac_keysize:]
        server_spec["mac_key"] = prf_seq[:mac_keysize]
        prf_seq = prf_seq[mac_keysize:]
        return

    def _sign_data(self, data, privkey):
        cryptography_imports()
        if isinstance(privkey, DSAPrivateKey):
            signer = privkey.signer(hashes.SHA256())
        elif isinstance(privkey, RSAPrivateKey):
            signer = privkey.signer(padding.PSS(padding.MGF1(hashes.SHA256()),
                                                padding.PSS.MAX_LENGTH),
                                    hashes.SHA256())
        elif isinstance(privkey, EllipticCurvePrivateKey):
            signer = privkey.signer(ec.ECDSA(hashes.SHA256()))
        else:
            raise SecSocketException("Unsupported Assymetric Key!")

        signer.update(data)
        return signer.finalize()

    def _verify_signature(self, pubkey, data, signature):
        cryptography_imports()
        if isinstance(pubkey, DSAPublicKey):
            verifier = pubkey.verifier(signature, hashes.SHA256())
        elif isinstance(pubkey, RSAPublicKey):
            verifier = pubkey.verifier(signature,
                                       padding.PSS(padding.MGF1(hashes.SHA256()),
                                                   padding.PSS.MAX_LENGTH),
                                       hashes.SHA256())
        elif isinstance(pubkey, EllipticCurvePublicKey):
            verifier = pubkey.verifier(signature, ec.ECDSA(hashes.SHA256()))
        else:
            raise SecSocketException("Unsupported Assymetric Key!")

        verifier.update(data)
        try:
            verifier.verify()
        except cryptography.exceptions.InvalidSignature:
            return False
        except:
            return False
        return True

    def _cmp_pub_keys(self, first, second):
        if first.public_numbers() != second.public_numbers():
            return False
        else:
            return True
