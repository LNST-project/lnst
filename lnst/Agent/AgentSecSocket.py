"""
The AgentSecSocket implements the agent (server) side of the handshake
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
import re
import logging
from lnst.Common.SecureSocket import SecureSocket
from lnst.Common.SecureSocket import DH_GROUP, SRP_GROUP
from lnst.Common.SecureSocket import SecSocketException
from lnst.Common.Utils import not_imported

ser = not_imported
load_pem_private_key = not_imported
load_pem_public_key = not_imported
load_ssh_public_key = not_imported
backend = not_imported
cryptography_imported = not_imported
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
        logging.error("Library 'cryptography' missing "\
                      "can't establish secure channel.")
        raise SecSocketException("Library 'cryptography' missing "\
                                 "can't establish secure channel.")

    backend = default_backend()
    cryptography_imported = True


class AgentSecSocket(SecureSocket):
    def __init__(self, soc):
        super(AgentSecSocket, self).__init__(soc)
        self._role = "server"

    def handshake(self, sec_params):
        ctl_hello = self.recv_msg()
        if ctl_hello["type"] != "ctl_hello":
            raise SecSocketException("Handshake failed.")

        self._ctl_random = ctl_hello["ctl_random"]
        self._slave_random = os.urandom(28)

        slave_hello = {"type": "slave_hello",
                       "slave_random": self._slave_random}
        self.send_msg(slave_hello)

        if sec_params["auth_types"] == "none":
            logging.warning("===================================")
            logging.warning("NO SECURE CHANNEL SETUP IS IN PLACE")
            logging.warning(" ALL COMMUNICATION IS IN PLAINTEXT")
            logging.warning("===================================")
            return True
        if sec_params["auth_types"] == "no-auth":
            logging.warning("===========================================")
            logging.warning("        NO AUTHENTICATION IN PLACE")
            logging.warning("SECURE CHANNEL IS VULNERABLE TO MIM ATTACKS")
            logging.warning("===========================================")
            cryptography_imports()
            self._dh_handshake()
        elif sec_params["auth_types"] == "ssh":
            cryptography_imports()
            self._ssh_handshake()
        elif sec_params["auth_types"] == "pubkey":
            cryptography_imports()
            srv_key = None
            try:
                with open(sec_params["privkey"], 'r') as f:
                    srv_key = load_pem_private_key(f.read(), None, backend)
            except:
                srv_key = None

            ctl_pubkeys = {}
            for fname in os.listdir(sec_params["ctl_pubkeys"]):
                path = os.path.join(sec_params["ctl_pubkeys"], fname)
                if not os.path.isfile(path):
                    continue
                try:
                    with open(path, 'r') as f:
                        ctl_pubkeys[fname] = load_pem_public_key(f.read(),
                                                                 backend)
                except:
                    continue

            self._pubkey_handshake(srv_key, ctl_pubkeys)
        elif sec_params["auth_types"] == "password":
            cryptography_imports()
            self._passwd_handshake(sec_params["auth_password"])
        else:
            raise SecSocketException("Unknown authentication method.")

    def _validate_secret(self, handshake_data):
        hashed_handshake_data = hashlib.sha256()
        hashed_handshake_data.update(handshake_data)

        srv_verify_data = self.PRF(self._master_secret,
                                   "server finished",
                                   hashed_handshake_data.digest(),
                                   12)

        finished_msg = {"type": "server finished",
                        "verify_data": srv_verify_data}
        self.send_msg(finished_msg)

        ctl_reply = self.recv_msg()
        if ctl_reply["type"] != "ctl finished":
            raise SecSocketException("Handshake failed.")

        ctl_verify_data = self.PRF(self._master_secret,
                                   "ctl finished",
                                   hashed_handshake_data.digest(),
                                   12)

        if ctl_verify_data != ctl_reply["verify_data"]:
            raise SecSocketException("Handshake failed.")
        return

    def _dh_handshake(self):
        modp_group = DH_GROUP
        #private exponent
        srv_privkey = int(os.urandom(modp_group["q_size"]+1).encode('hex'), 16)
        srv_privkey = srv_privkey % modp_group["q"]
        #public key
        srv_pubkey = pow(modp_group["g"], srv_privkey, modp_group["p"])

        msg = {"type": "pub_dh",
               "value": srv_pubkey}
        self.send_msg(msg)

        reply = self.recv_msg()
        if reply["type"] != "pub_dh":
            raise SecSocketException("Handshake failed.")

        ctl_pubkey = reply["value"]

        ZZ = pow(ctl_pubkey, srv_privkey, modp_group["p"])
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
        srv_keys = []
        srv_pubkeys = []
        authorized_keys = []
        sshd_key_paths = ["/etc/ssh/ssh_host_rsa_key",
                          "/etc/ssh/ssh_host_ecdsa_key"]
        ssh_dir_path = os.path.expanduser("~/.ssh")
        for f_name in sshd_key_paths:
            try:
                with open(f_name, 'r') as f:
                    srv_keys.append(load_pem_private_key(f.read(),
                                                         None,
                                                         backend))
                    srv_pubkeys.append(srv_keys[-1].public_key())
            except:
                continue

        if os.path.isfile(ssh_dir_path+"/authorized_keys"):
            with open(ssh_dir_path+"/authorized_keys", 'r') as f:
                for line in f.readlines():
                    try:
                        authorized_keys.append(load_ssh_public_key(line,
                                                                   backend))
                    except:
                        continue
        else:
            logging.error("No authorized keys loaded.")

        msg = self.recv_msg()
        if msg["type"] != "ssh_client_hello":
            raise SecSocketException("Handshake failed.")
        try:
            ctl_ssh_pubkey = load_pem_public_key(msg["ctl_ssh_pubkey"],
                                                 backend)
        except:
            raise SecSocketException("Handshake failed.")

        authorized = False
        for key in authorized_keys:
            if self._cmp_pub_keys(key, ctl_ssh_pubkey):
                authorized = True
                break
        if not authorized:
            raise SecSocketException("Handshake failed.")

        pem_pubkeys = []
        for key in srv_pubkeys:
            pem_key = key.public_bytes(
                            encoding=ser.Encoding.PEM,
                            format=ser.PublicFormat.SubjectPublicKeyInfo)
            pem_pubkeys.append(pem_key)

        msg = {"type": "ssh_server_hello",
               "srv_ssh_pubkeys": pem_pubkeys}
        self.send_msg(msg)

        msg = self.recv_msg()
        if msg["type"] != "ssh_client_key_select":
            raise SecSocketException("Handshake failed.")

        if not self._verify_signature(ctl_ssh_pubkey,
                                      str(msg["index"]),
                                      msg["signature"]):
            raise SecSocketException("Handshake failed.")

        self._pubkey_handshake(srv_keys[msg["index"]], {"ssh": ctl_ssh_pubkey})

    def _pubkey_handshake(self, srv_privkey, client_pubkeys):
        modp_group = DH_GROUP
        #private exponent
        srv_dh_privkey = int(os.urandom(modp_group["q_size"]+1).encode('hex'),
                             16)
        srv_dh_privkey = srv_dh_privkey % modp_group["q"]
        #public key
        srv_dh_pubkey_int = pow(modp_group["g"],
                                srv_dh_privkey,
                                modp_group["p"])
        srv_dh_pubkey = "{1:0{0}x}".format(modp_group['p_size']*2,
                                           srv_dh_pubkey_int)
        srv_dh_pubkey = srv_dh_pubkey.decode('hex')

        msg = self.recv_msg()
        if msg["type"] != "pubkey_client_hello":
            raise SecSocketException("Handshake failed.")
        ctl_identity = msg["identity"]
        try:
            ctl_pubkey = load_pem_public_key(msg["ctl_pubkey"], backend)
        except:
            raise SecSocketException("Handshake failed.")

        local_ctl_pubkey = client_pubkeys[ctl_identity]

        if not self._cmp_pub_keys(local_ctl_pubkey, ctl_pubkey):
            raise SecSocketException("Handshake failed.")

        ctl_dh_pubkey = msg["ctl_pub_dh"]
        signature = msg["signature"]
        if not self._verify_signature(local_ctl_pubkey,
                                      ctl_dh_pubkey,
                                      signature):
            raise SecSocketException("Handshake failed.")

        ctl_dh_pubkey_int = int(ctl_dh_pubkey.encode('hex'), 16)

        srv_pubkey = srv_privkey.public_key()
        srv_pubkey_pem = srv_pubkey.public_bytes(
                encoding=ser.Encoding.PEM,
                format=ser.PublicFormat.SubjectPublicKeyInfo)

        signature = self._sign_data(srv_dh_pubkey, srv_privkey)
        msg = {"type": "pubkey_server_hello",
               "srv_pubkey": srv_pubkey_pem,
               "srv_pub_dh": srv_dh_pubkey,
               "signature": signature}
        self.send_msg(msg)

        ZZ = pow(ctl_dh_pubkey_int, srv_dh_privkey, modp_group["p"])
        ZZ = "{1:0{0}x}".format(modp_group['p_size']*2, ZZ)
        ZZ = self._master_secret.decode('hex')

        self._master_secret = self.PRF(ZZ,
                                       "master secret",
                                       self._ctl_random + self._slave_random,
                                       48)

        self._init_cipher_spec()
        self._send_change_cipher_spec()

    def _passwd_handshake(self, auth_passwd):
        msg = self.recv_msg()
        if msg["type"] != "srp_client_begin":
            raise SecSocketException("Handshake failed.")

        if msg["username"] != "lnst_user":
            raise SecSocketException("Handshake failed.")

        srp_group = SRP_GROUP
        p_bytes = "{1:0{0}x}".format(srp_group['p_size']*2, srp_group['p'])
        p_bytes = p_bytes.decode('hex')
        g_bytes = "{0:02x}".format(srp_group['g'])
        g_bytes = g_bytes.decode('hex')
        k = hashlib.sha256(p_bytes + g_bytes).digest()
        k = int(k.encode('hex'), 16)
        username = msg["username"]

        salt = os.urandom(16)

        x = hashlib.sha256(salt + username + auth_passwd).digest()

        x_int = int(x.encode('hex'), 16)

        v = pow(srp_group["g"], x_int, srp_group["p"])

        msg = {"type": "srp_server_salt",
               "salt": salt}

        self.send_msg(msg)

        reply = self.recv_msg()
        if reply["type"] != "srp_client_pub":
            raise SecSocketException("Handshake failed.")

        ctl_pubkey = reply["ctl_pubkey"]
        ctl_pubkey_int = int(ctl_pubkey.encode('hex'), 16)

        if (ctl_pubkey_int % srp_group["p"]) == 0:
            raise SecSocketException("Handshake failed.")

        srv_privkey = os.urandom(srp_group["q_size"]+1)
        srv_privkey_int = int(srv_privkey.encode('hex'), 16) % srp_group["q"]

        srv_pubkey_int = pow(srp_group["g"], srv_privkey_int, srp_group["p"])
        srv_pubkey_int = (srv_pubkey_int + k*v) % srp_group["p"]
        srv_pubkey = "{1:0{0}x}".format(srp_group['p_size']*2, srv_pubkey_int)
        srv_pubkey = srv_pubkey.decode('hex')

        msg = {"type": "srp_server_pub",
               "srv_pubkey": srv_pubkey}
        self.send_msg(msg)

        u = hashlib.sha256(ctl_pubkey + srv_pubkey).digest()
        u_int = int(u.encode('hex'), 16)

        S_int = pow(v, u_int, srp_group['p'])*ctl_pubkey_int
        S_int = pow(S_int, srv_privkey_int, srp_group["p"])
        S = "{1:0{0}x}".format(srp_group['p_size']*2, S_int)
        S = S.decode('hex')

        msg = self.recv_msg()
        if msg["type"] != "srp_client_m1":
            raise SecSocketException("Handshake failed.")

        client_m1 = msg["m1"]

        srv_m1 = hashlib.sha256(ctl_pubkey + srv_pubkey + S).digest()
        if client_m1 != srv_m1:
            raise SecSocketException("Handshake failed.")

        srv_m2 = hashlib.sha256(ctl_pubkey + srv_m1 + S).digest()
        msg = {"type": "srp_server_m2",
               "m2": srv_m2}
        self.send_msg(msg)

        K = hashlib.sha256(S).digest()
        self._master_secret = self.PRF(K,
                                       "master secret",
                                       self._ctl_random + self._slave_random,
                                       48)

        self._init_cipher_spec()
        self._send_change_cipher_spec()
