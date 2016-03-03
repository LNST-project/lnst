"""
The CtlSecSocket implements the controller (client) side of the handshake
protocols.

Copyright 2016 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import hashlib
import math
import logging
from lnst.Common.SecureSocket import SecureSocket
from lnst.Common.SecureSocket import DH_GROUP, SRP_GROUP
from lnst.Common.SecureSocket import SecSocketException
from lnst.Common.Config import lnst_config

ser = None
load_pem_private_key = None
load_pem_public_key = None
load_ssh_public_key = None
backend = None
cryptography_imported = False
def cryptography_imports():
    global cryptography_imported
    if cryptography_imported:
        return

    global ser
    global load_pem_private_key
    global load_pem_public_key
    global load_ssh_public_key
    global backend

    try:
        import cryptography
        import cryptography.hazmat.primitives.serialization as ser
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.serialization import load_ssh_public_key
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        raise SecSocketException("Library 'cryptography' missing "\
                                 "can't establish secure channel.")

    backend = default_backend()
    cryptography_imported = True

class CtlSecSocket(SecureSocket):
    def __init__(self, soc):
        super(CtlSecSocket, self).__init__(soc)
        self._role = "client"

    def handshake(self, sec_params):
        self._ctl_random = os.urandom(28)

        ctl_hello = {"type": "ctl_hello",
                     "ctl_random": self._ctl_random}
        self.send_msg(ctl_hello)
        slave_hello = self.recv_msg()

        if slave_hello["type"] != "slave_hello":
            raise SecSocketException("Handshake failed.")

        self._slave_random = slave_hello["slave_random"]

        if sec_params["auth_type"] == "none":
            logging.warning("===================================")
            logging.warning("%s:%d" % self._socket.getpeername())
            logging.warning("NO SECURE CHANNEL SETUP IS IN PLACE")
            logging.warning(" ALL COMMUNICATION IS IN PLAINTEXT")
            logging.warning("===================================")
            return True
        if sec_params["auth_type"] == "no-auth":
            logging.warning("===========================================")
            logging.warning("        NO AUTHENTICATION IN PLACE")
            logging.warning("SECURE CHANNEL IS VULNERABLE TO MIM ATTACKS")
            logging.warning("===========================================")
            cryptography_imports()
            self._dh_handshake()
        elif sec_params["auth_type"] == "ssh":
            cryptography_imports()
            self._ssh_handshake()
        elif sec_params["auth_type"] == "pubkey":
            cryptography_imports()
            ctl_identity = sec_params["identity"]
            ctl_key_path = sec_params["privkey"]
            try:
                with open(ctl_key_path, 'r') as f:
                    ctl_key = load_pem_private_key(f.read(), None, backend)
            except:
                ctl_key = None

            srv_key_path = sec_params["pubkey_path"]
            try:
                with open(srv_key_path, 'r') as f:
                    srv_key = load_pem_public_key(f.read(), backend)
            except:
                srv_key = None

            if srv_key is None or ctl_key is None:
                raise SecSocketException("Handshake failed.")

            self._pubkey_handshake(ctl_identity, ctl_key, srv_key)
        elif sec_params["auth_type"] == "password":
            cryptography_imports()
            self._passwd_handshake(sec_params["auth_passwd"])
        else:
            raise SecSocketException("Unknown authentication method.")

    def _validate_secret(self, handshake_data):
        hashed_handshake_data = hashlib.sha256()
        hashed_handshake_data.update(handshake_data)

        ctl_verify_data = self.PRF(self._master_secret,
                                   "ctl finished",
                                   hashed_handshake_data.digest(),
                                   12)

        finished_msg = {"type": "ctl finished",
                        "verify_data": ctl_verify_data}
        self.send_msg(finished_msg)

        server_reply = self.recv_msg()
        if server_reply["type"] != "server finished":
            raise SecSocketException("Handshake failed.")

        srv_verify_data = self.PRF(self._master_secret,
                                   "server finished",
                                   hashed_handshake_data.digest(),
                                   12)

        if srv_verify_data != server_reply["verify_data"]:
            raise SecSocketException("Handshake failed.")
        return

    def _dh_handshake(self):
        modp_group = DH_GROUP
        #private exponent
        ctl_privkey = int(os.urandom(modp_group["q_size"]+1).encode('hex'), 16)
        ctl_privkey = ctl_privkey % modp_group["q"]
        #public key
        ctl_pubkey = pow(modp_group["g"], ctl_privkey, modp_group["p"])

        msg = {"type": "pub_dh",
               "value": ctl_pubkey}
        self.send_msg(msg)

        reply = self.recv_msg()
        if reply["type"] != "pub_dh":
            raise SecSocketException("Handshake failed.")

        srv_pubkey = reply["value"]

        ZZ = pow(srv_pubkey, ctl_privkey, modp_group["p"])
        ZZ = "{1:0{0}x}".format(modp_group['p_size']*2, ZZ)
        ZZ = self._master_secret.decode('hex')

        self._master_secret = self.PRF(ZZ,
                                       "master secret",
                                       self._ctl_random + self._slave_random,
                                       48)

        handshake_data = ""
        handshake_data += ("{1:0{0}x}".format(modp_group['p_size']*2,
                                              ctl_pubkey)).decode('hex')
        handshake_data += ("{1:0{0}x}".format(modp_group['p_size']*2,
                                              srv_pubkey)).decode('hex')

        self._init_cipher_spec()
        self._send_change_cipher_spec()
        self._validate_secret(handshake_data)

    def _ssh_handshake(self):
        ctl_ssh_key = None
        known_hosts = []
        ssh_dir_path = os.path.expanduser("~/.ssh")
        with open(ssh_dir_path+"/known_hosts", 'r') as f:
            for line in f.readlines():
                key = line[line.find(' ')+1:]
                known_hosts.append(load_ssh_public_key(key, backend))

        with open(ssh_dir_path+"/id_rsa", 'r') as f:
            ctl_ssh_key = load_pem_private_key(f.read(), None, backend)

        if not ctl_ssh_key:
            raise SecSocketException("Handshake failed.")

        ctl_ssh_pubkey = ctl_ssh_key.public_key()
        ctl_ssh_pubkey_pem = ctl_ssh_pubkey.public_bytes(
                encoding=ser.Encoding.PEM,
                format=ser.PublicFormat.SubjectPublicKeyInfo)
        msg = {"type": "ssh_client_hello",
               "ctl_ssh_pubkey": ctl_ssh_pubkey_pem}

        self.send_msg(msg)
        msg = self.recv_msg()
        if msg["type"] != "ssh_server_hello":
            raise SecSocketException("Handshake failed.")
        srv_ssh_pubkeys = []
        for key in msg["srv_ssh_pubkeys"]:
            srv_ssh_pubkeys.append(load_pem_public_key(key, backend))

        srv_ssh_pubkey = None
        i = 0
        for key in srv_ssh_pubkeys:
            for host in known_hosts:
                if self._cmp_pub_keys(key, host):
                    srv_ssh_pubkey = host
                    break
            if srv_ssh_pubkey is not None:
                break
            i += 1
        if not srv_ssh_pubkey:
            raise SecSocketException("Handshake failed.")

        msg = {"type": "ssh_client_key_select",
               "index": i,
               "signature": self._sign_data(str(i), ctl_ssh_key)}
        self.send_msg(msg)

        self._pubkey_handshake("ssh", ctl_ssh_key, srv_ssh_pubkey)

    def _pubkey_handshake(self, ctl_identity, ctl_privkey, local_srv_pubkey):
        modp_group = DH_GROUP
        ctl_dh_privkey = int(os.urandom(modp_group["q_size"]+1).encode('hex'),
                             16)
        ctl_dh_privkey = ctl_dh_privkey % modp_group["q"]
        #public key
        ctl_dh_pubkey_int = pow(modp_group["g"],
                                ctl_dh_privkey,
                                modp_group["p"])
        ctl_dh_pubkey = "{1:0{0}x}".format(modp_group['p_size']*2,
                                           ctl_dh_pubkey_int)
        ctl_dh_pubkey = ctl_dh_pubkey.decode('hex')

        ctl_pubkey = ctl_privkey.public_key()
        ctl_pubkey_pem = ctl_pubkey.public_bytes(
                encoding=ser.Encoding.PEM,
                format=ser.PublicFormat.SubjectPublicKeyInfo)

        signature = self._sign_data(ctl_dh_pubkey, ctl_privkey)
        msg = {"type": "pubkey_client_hello",
               "identity": ctl_identity,
               "ctl_pubkey": ctl_pubkey_pem,
               "ctl_pub_dh": ctl_dh_pubkey,
               "signature": signature}

        self.send_msg(msg)

        msg = self.recv_msg()
        if msg["type"] != "pubkey_server_hello":
            raise SecSocketException("Handshake failed.")

        srv_pubkey = load_pem_public_key(msg["srv_pubkey"], backend)
        if not self._cmp_pub_keys(local_srv_pubkey, srv_pubkey):
            raise SecSocketException("Handshake failed.")

        srv_dh_pubkey = msg["srv_pub_dh"]
        if not self._verify_signature(local_srv_pubkey,
                                      srv_dh_pubkey,
                                      msg["signature"]):
            raise SecSocketException("Handshake failed.")

        srv_dh_pubkey_int = int(srv_dh_pubkey.encode('hex'), 16)

        ZZ = pow(srv_dh_pubkey_int, ctl_dh_privkey, modp_group["p"])
        ZZ = "{1:0{0}x}".format(modp_group['p_size']*2, ZZ)
        ZZ = self._master_secret.decode('hex')

        self._master_secret = self.PRF(ZZ,
                                       "master secret",
                                       self._ctl_random + self._slave_random,
                                       48)

        self._init_cipher_spec()
        self._send_change_cipher_spec()

    def _passwd_handshake(self, auth_passwd):
        srp_group = SRP_GROUP
        p_bytes = "{1:0{0}x}".format(srp_group['p_size']*2, srp_group['p'])
        p_bytes = p_bytes.decode('hex')
        g_bytes = "{0:02x}".format(srp_group['g'])
        g_bytes = g_bytes.decode('hex')
        k = hashlib.sha256(p_bytes + g_bytes).digest()
        k = int(k.encode('hex'), 16)

        username = "lnst_user"

        msg = {"type": "srp_client_begin",
               "username": username}
        self.send_msg(msg)

        reply = self.recv_msg()
        if reply["type"] != "srp_server_salt":
            raise SecSocketException("Handshake failed.")

        salt = reply["salt"]

        x = hashlib.sha256(salt + username + auth_passwd).digest()
        x_int = int(x.encode('hex'), 16)

        ctl_privkey = os.urandom(srp_group["q_size"]+1)
        ctl_privkey_int = int(ctl_privkey.encode('hex'), 16) % srp_group["q"]

        ctl_pubkey_int = pow(srp_group["g"], ctl_privkey_int, srp_group["p"])
        ctl_pubkey = "{1:0{0}x}".format(srp_group['p_size']*2, ctl_pubkey_int)
        ctl_pubkey = ctl_pubkey.decode('hex')

        msg = {"type": "srp_client_pub",
               "ctl_pubkey": ctl_pubkey}
        self.send_msg(msg)

        reply = self.recv_msg()
        if reply["type"] != "srp_server_pub":
            raise SecSocketException("Handshake failed.")

        srv_pubkey = reply["srv_pubkey"]
        srv_pubkey_int = int(srv_pubkey.encode('hex'), 16)

        if (srv_pubkey_int % srp_group["p"]) == 0:
            raise SecSocketException("Handshake failed.")

        u = hashlib.sha256(ctl_pubkey + srv_pubkey).digest()
        u_int = int(u.encode('hex'), 16)

        S_int = srv_pubkey_int - k * pow(srp_group['g'], x_int, srp_group['p'])
        S_int = pow(S_int, ctl_privkey_int + u_int * x_int, srp_group['p'])
        S = "{1:0{0}x}".format(srp_group['p_size']*2, S_int)
        S = S.decode('hex')

        m1 = hashlib.sha256(ctl_pubkey + srv_pubkey + S).digest()
        msg = {"type": "srp_client_m1",
               "m1": m1}
        self.send_msg(msg)

        reply = self.recv_msg()
        if reply["type"] != "srp_server_m2":
            raise SecSocketException("Handshake failed.")
        srv_m2 = reply["m2"]

        client_m2 = hashlib.sha256(ctl_pubkey + m1 + S).digest()
        if srv_m2 != client_m2:
            raise SecSocketException("Handshake failed.")

        K = hashlib.sha256(S).digest()
        self._master_secret = self.PRF(K,
                                       "master secret",
                                       self._ctl_random + self._slave_random,
                                       48)

        self._init_cipher_spec()
        self._send_change_cipher_spec()
