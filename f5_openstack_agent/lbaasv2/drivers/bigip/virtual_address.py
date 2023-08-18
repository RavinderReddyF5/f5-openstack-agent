# coding=utf-8
# Copyright (c) 2014-2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper


LOG = logging.getLogger(__name__)


class VirtualAddress(object):
    u"""Class to translate LBaaS loadbalancer objects to BIG-IP virtual address.

    Creates BIG-IP virtual address objects given an LBaaS service object.
    """

    def __init__(self, adapter, loadbalancer):

        self.adapter = adapter
        self.virtual_address = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual_address)

        # Immutable attributes
        self.name = self.adapter.prefix + loadbalancer['id']
        self.partition = self.adapter.get_folder_name(
            loadbalancer['tenant_id'])
        self.address = loadbalancer.get('vip_address', "")

        # Mutable attributes
        self.description = self.adapter.get_resource_description(loadbalancer)
        self.traffic_group = loadbalancer.get('traffic_group', "")

        self.auto_delete = False

        if loadbalancer.get('admin_state_up', True):
            self.enabled = 'yes'
        else:
            self.enabled = 'no'

        self.ct_limit = self.get_connection_limit(loadbalancer)

    def model(self):
        model = {"name": self.name,
                 "partition": self.partition,
                 "address": self.address,
                 "description": self.description,
                 "trafficGroup": self.traffic_group,
                 "autoDelete": self.auto_delete,
                 "enabled": self.enabled,
                 "connectionLimit": self.ct_limit}

        return model

    def create(self, bigip, model=None):
        if not model:
            model = self.model()

        self.virtual_address.create(bigip, model)

    def exists(self, bigip):
        return self.virtual_address.exists(
            bigip,
            name=self.name,
            partition=self.partition)

    def delete(self, bigip):
        self.virtual_address.delete(
            bigip,
            name=self.name,
            partition=self.partition)

    def load(self, bigip):
        return self.virtual_address.load(
            bigip,
            name=self.name,
            partition=self.partition)

    def update(self, bigip):

        # Get the model object, pop immutables and update
        model = self.model()
        remote = self.load(bigip)
        if remote.address != model.get('address', ''):
            # Could be Route Domain or IP has changed
            try:
                self.delete(bigip)
            except Exception as Error:
                LOG.error('Failed to delete redunant virtual address "{}"'
                          ' for {}'.format(Error, remote))
            va = self.create(bigip)
        else:
            model.pop("address")
            va = self.virtual_address.update(bigip, model)
        return va

    def assure(self, bigip, delete=False):

        if delete:
            self.delete(bigip)
        elif not self.exists(bigip):
            self.create(bigip)

    def get_connection_limit(self, loadbalancer):
        ct_limit = 0
        flavor = loadbalancer.get("flavor")
        if flavor is not None:

            if str(flavor) not in constants_v2.FLAVOR_CONN_MAP:
                LOG.warn(
                    "Cannot find flavor %s in flavor map %s" % (
                        flavor, constants_v2.FLAVOR_CONN_MAP
                    )
                )
                # pzhang: give a number to cause lb create/update
                # error
                return -100

            ct_limit = constants_v2.FLAVOR_CONN_MAP[
                str(flavor)]['connection_limit']

        # Overwrite the default value for flavor 21 only
        if flavor == 21:
            ct_limit = loadbalancer.get("max_concurrency", ct_limit)

        return ct_limit
