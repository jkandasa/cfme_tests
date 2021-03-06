# -*- coding: utf-8 -*-
import attr

from navmazing import NavigateToSibling, NavigateToAttribute
from widgetastic_manageiq import (
    Accordion,
    BaseEntitiesView,
    BootstrapSelect,
    BootstrapSwitch,
    BreadCrumb,
    ItemsToolBarViewSelector,
    ManageIQTree,
    SummaryTable,
    TextInput,
)
from widgetastic_patternfly import Button, Dropdown
from widgetastic.widget import View, Text

from cfme.base.ui import BaseLoggedInPage
from cfme.exceptions import VolumeNotFoundError, ItemNotFound
from cfme.utils.appliance.implementations.ui import CFMENavigateStep, navigator, navigate_to
from cfme.modeling.base import BaseCollection, BaseEntity
from cfme.utils.log import logger
from cfme.utils.wait import wait_for, TimedOutError


class VolumeToolbar(View):
    configuration = Dropdown('Configuration')
    policy = Dropdown('Policy')
    download = Dropdown('Download')  # title match
    view_selector = View.nested(ItemsToolBarViewSelector)


class VolumeDetailsToolbar(View):
    configuration = Dropdown('Configuration')
    policy = Dropdown('Policy')
    download = Button('Download summary in PDF format')


class VolumeDetailsEntities(View):
    breadcrumb = BreadCrumb()
    title = Text('//div[@id="main-content"]//h1')
    properties = SummaryTable('Properties')
    relationships = SummaryTable('Relationships')
    smart_management = SummaryTable('Smart Management')


class VolumeDetailsAccordion(View):
    @View.nested
    class properties(Accordion):  # noqa
        tree = ManageIQTree()

    @View.nested
    class relationships(Accordion):  # noqa
        tree = ManageIQTree()


class VolumeView(BaseLoggedInPage):
    """Base class for header and nav check"""
    @property
    def in_volume(self):
        return (
            self.logged_in_as_current_user and
            self.navigation.currently_selected == ['Storage', 'Block Storage', 'Volumes'])


class VolumeAllView(VolumeView):
    toolbar = View.nested(VolumeToolbar)
    including_entities = View.include(BaseEntitiesView, use_parent=True)

    @property
    def is_displayed(self):
        return (
            self.in_volume and
            self.entities.title.text == 'Cloud Volumes'
        )


class VolumeDetailsView(VolumeView):
    @property
    def is_displayed(self):
        expected_title = '{} (Summary)'.format(self.context['object'].name)
        # The field in relationships table changes based on volume status so look for either
        try:
            provider = self.entities.relationships.get_text_of('Cloud Provider')
        except NameError:
            provider = self.entities.relationships.get_text_of('Parent Cloud Provider')
        return (
            self.in_volume and
            self.entities.title.text == expected_title and
            self.entities.breadcrumb.active_location == expected_title and
            provider == self.context['object'].provider.name)

    toolbar = View.nested(VolumeDetailsToolbar)
    sidebar = View.nested(VolumeDetailsAccordion)
    entities = View.nested(VolumeDetailsEntities)


class VolumeAddEntities(View):
    breadcrumb = BreadCrumb()
    title = Text('//div[@id="main-content"]//h1')


class VolumeAddForm(View):
    storage_manager = BootstrapSelect(name='storage_manager_id')
    volume_name = TextInput(name='name')
    size = TextInput(name='size')
    tenant = BootstrapSelect(name='cloud_tenant_id')
    add = Button('Add')
    cancel = Button('Cancel')


class VolumeAddView(VolumeView):
    @property
    def is_displayed(self):
        expected_title = "Add New Cloud Volume"
        return (
            self.in_volume and
            self.entities.title.text == expected_title and
            self.entities.breadcrumb.active_location == expected_title)

    entities = View.nested(VolumeAddEntities)
    form = View.nested(VolumeAddForm)


class VolumeEditView(VolumeView):
    @property
    def is_displayed(self):
        return False

    volume_name = TextInput(name='name')
    save = Button('Save')


class VolumeBackupView(VolumeView):
    @property
    def is_displayed(self):
        return False

    backup_name = TextInput(name='backup_name')
    # options
    incremental = BootstrapSwitch(name='incremental')
    force = BootstrapSwitch(name='force')

    save = Button('Save')
    reset = Button('Reset')
    cancel = Button('Cancel')


@attr.s
class Volume(BaseEntity):

    name = attr.ib()
    provider = attr.ib()

    def wait_for_disappear(self, timeout=300):
        """Wait for disappear the volume"""
        try:
            wait_for(lambda: not self.exists,
                     timeout=timeout,
                     message='Wait for cloud Volume to disappear',
                     delay=20,
                     fail_func=self.refresh)
        except TimedOutError:
            logger.error('Timed out waiting for Volume to disappear, continuing')

    def edit(self, name):
        """Edit cloud volume"""
        view = navigate_to(self, 'Edit')
        view.volume_name.fill(name)
        view.save.click()

        view.flash.assert_success_message('Cloud Volume "{}" updated'.format(name))

        self.name = name
        wait_for(lambda: self.exists, delay=20, timeout=500, fail_func=self.refresh)

    def delete(self, wait=True):
        """Delete the Volume"""

        view = navigate_to(self, 'Details')
        view.toolbar.configuration.item_select('Delete this Cloud Volume', handle_alert=True)
        view.flash.assert_success_message('Delete initiated for 1 Cloud Volume.')

        if wait:
            self.wait_for_disappear(500)

    def refresh(self):
        """Refresh provider relationships and browser"""
        self.provider.refresh_provider_relationships()
        self.browser.refresh()

    def create_backup(self, name, incremental=None, force=None):
        """create backup of cloud volume"""
        view = navigate_to(self, 'Backup')
        view.backup_name.fill(name)
        view.incremental.fill(incremental)
        view.force.fill(force)

        view.save.click()
        view.flash.assert_success_message('Backup for Cloud Volume "{}" created'.format(self.name))

        wait_for(lambda: self.backups > 0, delay=20, timeout=1000, fail_func=self.refresh)

    @property
    def exists(self):
        try:
            navigate_to(self, 'Details')
            return True
        except VolumeNotFoundError:
            return False

    @property
    def size(self):
        """ size of storage cloud volume.

        Returns:
            :py:class:`str' size of volume.
        """
        view = navigate_to(self, 'Details')
        return view.entities.properties.get_text_of('Size')

    @property
    def tenant(self):
        """ cloud tenants for volume.

        Returns:
            :py:class:`str' respective tenants.
        """
        view = navigate_to(self, 'Details')
        return view.entities.relationships.get_text_of('Cloud Tenants')

    @property
    def backups(self):
        """ number of available backups for volume.

        Returns:
            :py:class:`int' backup count.
        """
        view = navigate_to(self, 'Details')
        return int(view.entities.relationships.get_text_of('Cloud Volume Backups'))


@attr.s
class VolumeCollection(BaseCollection):
    """Collection object for the :py:class:'cfme.storage.volume.Volume'. """
    ENTITY = Volume

    def create(self, name, storage_manager, tenant, size, provider):
        """Create new storage volume

        Args:
            name: volume name
            storage_manager: storage manager name
            tenant: tenant name
            size: volume size in GB
            provider: provider

        Returns:
            object for the :py:class: cfme.storage.volume.Volume
        """

        view = navigate_to(self, 'Add')
        view.form.fill({'storage_manager': storage_manager,
                        'tenant': tenant,
                        'volume_name': name,
                        'size': size})
        view.form.add.click()
        base_message = 'Cloud Volume "{}" created'
        view.flash.assert_success_message(base_message.format(name))

        volume = self.instantiate(name, provider)
        wait_for(lambda: volume.exists, delay=20, timeout=500, fail_func=volume.refresh)

        return volume

    def delete(self, *volumes):
        """Delete one or more Volumes from list of Volumes

        Args:
            One or Multiple 'cfme.storage.volume.Volume' objects
        """

        view = navigate_to(self, 'All')

        if view.entities.get_all():
            for volume in volumes:
                try:
                    view.entities.get_entity(name=volume.name).check()
                except ItemNotFound:
                    raise VolumeNotFoundError("Volume {} not found".format(volume.name))

            view.toolbar.configuration.item_select('Delete selected Cloud Volumes',
                                                   handle_alert=True)

            for volume in volumes:
                volume.wait_for_disappear()
        else:
            raise VolumeNotFoundError('No Cloud Volume for Deletion')


@navigator.register(VolumeCollection, 'All')
class VolumeAll(CFMENavigateStep):
    VIEW = VolumeAllView
    prerequisite = NavigateToAttribute('appliance.server', 'LoggedIn')

    def step(self, *args, **kwargs):
        self.prerequisite_view.navigation.select('Storage', 'Block Storage', 'Volumes')


@navigator.register(Volume, 'Details')
class VolumeDetails(CFMENavigateStep):
    VIEW = VolumeDetailsView
    prerequisite = NavigateToAttribute('parent', 'All')

    def step(self, *args, **kwargs):

        try:
            self.prerequisite_view.entities.get_entity(name=self.obj.name,
                                                       surf_pages=True).click()

        except ItemNotFound:
            raise VolumeNotFoundError('Volume {} not found'.format(self.obj.name))


@navigator.register(VolumeCollection, 'Add')
class VolumeAdd(CFMENavigateStep):
    VIEW = VolumeAddView
    prerequisite = NavigateToSibling('All')

    def step(self, *args, **kwargs):
        self.prerequisite_view.toolbar.configuration.item_select('Add a new Cloud Volume')


@navigator.register(Volume, 'Edit')
class VolumeEdit(CFMENavigateStep):
    VIEW = VolumeEditView
    prerequisite = NavigateToSibling('Details')

    def step(self, *args, **kwargs):
        self.prerequisite_view.toolbar.configuration.item_select('Edit this Cloud Volume')


@navigator.register(Volume, 'Backup')
class VolumeBackup(CFMENavigateStep):
    VIEW = VolumeBackupView
    prerequisite = NavigateToSibling('Details')

    def step(self, *args, **kwargs):
        self.prerequisite_view.toolbar.configuration.item_select('Create a Backup of this Cloud '
                                                                 'Volume')
