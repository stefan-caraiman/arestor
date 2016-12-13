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

# pylint: disable=invalid-name

"""Arestor API endpoint for resource management."""

import cherrypy

from arestor.api import base as base_api


class ResourceEndpoint(base_api.Resource):

    exposed = True

    """Resource management endpoint."""

    @cherrypy.tools.user_required()
    def GET(self, resource_id=None, status=True, verbose='OK'):
        """The representation of userdata resource."""
        response = {
            "meta": {"status": status, "verbose": verbose},
            "content": None
        }

        if not response["meta"]["status"]:
            cherrypy.response.status = 400
            return response

        if not resource_id:
            # Prepare a list with all the available resources.
            pass
        else:
            # Prepare the representation of the received resource.
            pass

    @cherrypy.tools.user_required()
    def POST(self, **content):
        """Create a new resource."""
        pass

    @cherrypy.tools.user_required()
    def PUT(self, resource_id, **content):
        """Update the required resource."""
        pass

    @cherrypy.tools.user_required()
    def DELETE(self, resource_id):
        """Delete the required resource."""
        pass
