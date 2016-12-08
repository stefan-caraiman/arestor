# Copyright 2016 Cloudbase Solutions Srl
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""A collection of utilities used across the project."""

import base64
import hashlib
import json

import cherrypy
from Crypto.Cipher import AES
from Crypto import Random
from oslo_log import log as logging
import redis

from arestor.common import exception
from arestor import config as arestor_config

CONFIG = arestor_config.CONFIG
LOG = logging.getLogger(__name__)


def get_attribute(root, attribute):
    """Search for the received attribute name in the object tree.

    :param root: the root object
    :param attribute: the name of the required attribute
    """
    command_tree = [root]
    while command_tree:
        current_object = command_tree.pop()
        if hasattr(current_object, attribute):
            return getattr(current_object, attribute)

        parent = getattr(current_object, "parent", None)
        if parent:
            command_tree.append(parent)

    raise exception.ArestorException("The %(attribute)r attribute is "
                                     "missing from the object tree.",
                                     attribute=attribute)


class AESCipher(object):

    """Wrapper over AES Cipher."""

    def __init__(self, key):
        """Setup the new instance."""
        self._block_size = AES.block_size
        self._key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, message):
        """Encrypt the received message."""
        message = self._padding(message, self._block_size)
        initialization_vector = Random.new().read(self._block_size)
        cipher = AES.new(self._key, AES.MODE_CBC, initialization_vector)
        return base64.b64encode(initialization_vector +
                                cipher.encrypt(message))

    def decrypt(self, message):
        """Decrypt the received message."""
        message = base64.b64decode(message)
        initialization_vector = message[:self._block_size]
        cipher = AES.new(self._key, AES.MODE_CBC, initialization_vector)
        raw_message = cipher.decrypt(message[self._block_size:])
        return self._remove_padding(raw_message).decode('utf-8')

    @staticmethod
    def _padding(message, block_size):
        """Add padding."""
        return (message + (block_size - len(message) % block_size) *
                chr(block_size - len(message) % block_size))

    @staticmethod
    def _remove_padding(message):
        """Remove the padding."""
        return message[:-ord(message[len(message) - 1:])]


class RedisConnection(object):

    """High level wrapper over the redis data structures operations."""

    def __init__(self):
        """Instantiates objects able to store and retrieve data."""
        self._rcon = None
        self._host = CONFIG.redis.host
        self._port = CONFIG.redis.port
        self._db = CONFIG.redis.database
        self.refresh()

    def _connect(self):
        """Try establishing a connection until succeeds."""
        try:
            rcon = redis.StrictRedis(self._host, self._port, self._db)
            # return the connection only if is valid and reachable
            if not rcon.ping():
                return None
        except (redis.ConnectionError, redis.RedisError):
            return None
        return rcon

    def refresh(self, tries=3):
        """Re-establish the connection only if is dropped."""
        for _ in range(tries):
            try:
                if not self._rcon or not self._rcon.ping():
                    self._rcon = self._connect()
                else:
                    break
            except redis.ConnectionError:
                pass
        else:
            raise redis.ConnectionError("Connection refused.")

        return True

    @property
    def rcon(self):
        """Return a Redis connection."""
        self.refresh()
        return self._rcon

    def get_secret(self, api_key):
        """Get the secret for the user with received api key."""
        return self.rcon.hget("user.secret", api_key)

    def get_user(self, api_key):
        """Get information regarding user which has received api key."""
        return json.load(self.rcon.hget("user.info", api_key))


class UserManager(cherrypy.Tool):

    """Check if the request is valid and the resource is available."""

    def __init__(self):
        """Setup the new instance."""
        super(UserManager, self).__init__('before_handler', self.load,
                                          priority=10)
        self._redis = RedisConnection()

    @staticmethod
    def _process_content(secret):
        """Get information from request and update request params."""
        request = cherrypy.request
        content = request.params.pop('content', None)
        if not content:
            return True

        cipher = AESCipher(secret)
        try:
            params = json.loads(cipher.decrypt(content))
        except ValueError as exc:
            LOG.error("Failed to decrypt content: %s", exc)
            return False

        if not isinstance(params, dict):
            LOG.error("Invalid content type provided: %s", type(params))
            return False

        for key, value in params.items():
            request.params[key] = value

        return True

    def load(self):
        """Process information received from client."""
        request = cherrypy.request
        api_key = request.params.get('api_key')
        secret = self._redis.get_secret(api_key)

        request.params["status"] = False
        request.params["verbose"] = "OK"

        if not secret:
            request.params["verbose"] = "Invalid api key provided."
            return

        if not self._process_content(secret):
            request.params["verbose"] = "Invalid request."
            return

        request.params["status"] = True
