# -*- coding: utf-8 -*-

import pytest
import re
from cfme.fixtures import pytest_selenium as sel
from cfme import test_requirements
from cfme.infrastructure.provider import InfraProvider
import cfme.web_ui.toolbar as tb
from cfme.web_ui import ButtonGroup, form_buttons, Quadicon, fill
from utils.appliance.implementations.ui import navigate_to
from utils.providers import setup_a_provider as _setup_a_provider
from cfme.configure import settings  # NOQA
from cfme.services.catalogs import catalog_item  # NOQA
from cfme.services import workloads  # NOQA
from cfme.intelligence.reports.reports import CannedSavedReport

pytestmark = [pytest.mark.tier(3),
              test_requirements.settings]


# TODO: infrastructure hosts, pools, stores, clusters, catalog_items are removed
#  due to navmazing. all items have to be put back once navigation change is fully done

gtl_params = {
    'Infrastructure Providers': InfraProvider,
    'VMs': 'infra_vms',
    'My Services': 'my_services',
    # 'Catalog Items/catalog_items',
    'VMs & Instances': 'service_vms_instances',
    'Templates & Images': 'service_templates_images'
}

gtl_parametrize = pytest.mark.parametrize('key', gtl_params, scope="module")


def select_two_quads():
    count = 0
    for quad in Quadicon.all("infra_prov", this_page=True):
        count += 1
        if count > 2:
            break
        fill(quad.checkbox(), True)


@pytest.fixture(scope="module")
def setup_a_provider():
    _setup_a_provider(prov_class="infra", validate=True, check_existing=True)


def set_view(group, button):
    bg = ButtonGroup(group)
    if bg.active != button:
        bg.choose(button)
        sel.click(form_buttons.save)


def reset_default_view(name, default_view):
    bg = ButtonGroup(name)
    sel.force_navigate("my_settings_default_views")
    if bg.active != default_view:
        bg.choose(default_view)
        sel.click(form_buttons.save)


def get_default_view(name):
    bg = ButtonGroup(name)
    pytest.sel.force_navigate("my_settings_default_views")
    default_view = bg.active
    return default_view


def set_and_test_default_view(group_name, view, page):
    default_view = get_default_view(group_name)
    set_view(group_name, view)
    if isinstance(basestring, page):
        sel.force_navigate(page)
    else:
        navigate_to(page, 'All', use_resetter=False)
    assert tb.is_active(view), "{} view setting failed".format(view)
    reset_default_view(group_name, default_view)


@pytest.mark.parametrize('key', gtl_params, scope="module")
def test_tile_defaultview(request, setup_a_provider, key):
    name = re.split(r"\/", key)
    set_and_test_default_view(name[0], 'Tile View', name[1])


@pytest.mark.parametrize('key', gtl_params, scope="module")
def test_list_defaultview(request, setup_a_provider, key):
    name = re.split(r"\/", key)
    set_and_test_default_view(name[0], 'List View', name[1])


@pytest.mark.parametrize('key', gtl_params, scope="module")
def test_grid_defaultview(request, setup_a_provider, key):
    name = re.split(r"\/", key)
    set_and_test_default_view(name[0], 'Grid View', name[1])


def set_and_test_view(group_name, view):
    default_view = get_default_view(group_name)
    set_view(group_name, view)
    sel.force_navigate('infrastructure_virtual_machines')
    select_two_quads()
    tb.select('Configuration', 'Compare Selected items')
    assert tb.is_active(view), "{} setting failed".format(view)
    reset_default_view(group_name, default_view)


@pytest.mark.meta(blockers=[1394331])
def test_expanded_view(request, setup_a_provider):
    set_and_test_view('Compare', 'Expanded View')


@pytest.mark.meta(blockers=[1394331])
def test_compressed_view(request, setup_a_provider):
    set_and_test_view('Compare', 'Compressed View')


@pytest.mark.meta(blockers=[1394331])
def test_details_view(request, setup_a_provider):
    set_and_test_view('Compare Mode', 'Details Mode')


@pytest.mark.meta(blockers=[1394331])
def test_exists_view(request, setup_a_provider):
    set_and_test_view('Compare Mode', 'Exists Mode')


def test_hybrid_view(request, setup_a_provider):
    path = ["Configuration Management", "Hosts", "Virtual Infrastructure Platforms"]
    report = CannedSavedReport.new(path)
    report.navigate()
    tb.select('Hybrid View')
    assert tb.is_active('Hybrid View'), "Hybrid view setting failed"


def test_graph_view(request, setup_a_provider):
    path = ["Configuration Management", "Hosts", "Virtual Infrastructure Platforms"]
    report = CannedSavedReport.new(path)
    report.navigate()
    tb.select('Graph View')
    assert tb.is_active('Graph View'), "Graph view setting failed"


def test_tabular_view(request, setup_a_provider):
    path = ["Configuration Management", "Hosts", "Virtual Infrastructure Platforms"]
    report = CannedSavedReport.new(path)
    report.navigate()
    tb.select('Tabular View')
    assert tb.is_active('Tabular View'), "Tabular view setting failed"
