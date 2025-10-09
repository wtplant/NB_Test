from os import getenv
import os
from extras.scripts import *

from dcim.choices import InterfaceModeChoices, InterfaceTypeChoices
import re
from dcim.models import Device, DeviceType, Interface, Manufacturer, Site, DeviceRole
import time
import requests, urllib3
from ipam.models import VLAN
from utilities.exceptions import AbortScript

# Test function Import
from django.test import TestCase
from django.test import tag
import traceback


@tag("rkt_test")
class TestBuildTestDevices(TestCase):
    def test_script(self):
        class_to_test = BuildTestDevices()
        class_to_test.run({"device_count": 50, "interface_count": 48, "vlan_count": 500}, True)
        devices = Device.objects.filter(tags__name="VLAN_TEST_SYNC_TAG")
        self.assertEqual(devices.count(), 50)
        for device in devices:
            self.assertEqual(device.interfaces.count(), 48)
        vlans = VLAN.objects.filter(tags__name="VLAN_TEST_SYNC_TAG")
        self.assertEqual(vlans.count(), 500)


class BuildTestDevices(Script):
    class Meta:
        name = "1 - Build dummy Devices"
        scheduling_enabled = False
        description = "Build Dummy Devices for testing"
        job_timeout = 60 * 60 * 8

    default_device_count = 10
    default_interface_count = 10
    default_vlan_count = 500
    device_count = IntegerVar(
        description="Number of Devices to Create",
        default=default_device_count,
    )
    interface_count = IntegerVar(
        description="Number of Interfaces to Create",
        default=default_interface_count,
    )
    vlan_count = IntegerVar(
        description="Number of Interfaces to Create",
        default=default_vlan_count,
    )
    # Debug Flag - will remain expose to the end user do to the complexity of the script - best to allow the user to enable it
    debug = BooleanVar(
        description="Debug Mode",
        default=str(getenv("DEBUG")).lower() == "true",
    )

    # Flag to enable debug logging
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.DEBUG = False
        self.ROCKET_IN_CIDI_TEST_ENVIRONMENT = getenv("ROCKET_IN_CIDI_TEST_ENVIRONMENT", "False").lower() == "true"

    def log_debug(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_debug(message, obj)

    def log_info(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_info(message, obj)

    def log_success(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_success(message, obj)

    def run(self, data: dict, commit: bool):
        vlan_sync_tag = "VLAN_TEST_SYNC_TAG"
        # if not self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
        #     raise AbortScript("This script can only be run in the CIDI Test Environment - PROD BLOCKED")
        if data.get("debug", False) or self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            self.DEBUG = True
        if data.get("device_count", 0) == 0:
            data["device_count"] = self.default_device_count
        if data.get("interface_count", 0) == 0:
            data["interface_count"] = self.default_interface_count
        if data.get("vlan_count", 0) == 0:
            data["vlan_count"] = self.default_vlan_count
        role, _ = DeviceRole.objects.get_or_create(name="Test Device Role")
        site, _ = Site.objects.get_or_create(name="Test Site")
        manufacturer, _ = Manufacturer.objects.get_or_create(name="Test Manufacturer")
        device_type, _ = DeviceType.objects.get_or_create(model="Test Device Type", manufacturer=manufacturer)
        for i in range(data.get("vlan_count")):
            id = i + 1
            # self.log_debug(f"vlan.get_or_create(vid={id}, name=VLAN{id}, site={site})")
            vlan, _ = VLAN.objects.get_or_create(
                vid=id,
                name=f"VLAN{id}",
                site=site,
            )
            vlan.full_clean()
            vlan.save()
            vlan.tags.add(vlan_sync_tag)
            # self.log_debug(f"Created VLAN{i}", obj=vlan)
        self.log_success(f"Created {data.get('vlan_count')} VLANs")
        for i in range(data.get("device_count")):
            id = i + 1
            self.log_debug(f"Creating Device {id:03d}")
            device, _ = Device.objects.get_or_create(
                name=f"test-device-{id:03d}",
                device_type=device_type,
                site=site,
                role=role,
            )
            device.full_clean()
            device.save()
            device.tags.add(vlan_sync_tag)
            self.log_success(f"Created Device {device.name}", obj=device)
            for j in range(data.get("interface_count")):
                id = j + 1
                # self.log_debug(f"Creating Interface {id}")
                interface, _ = Interface.objects.get_or_create(
                    device=device,
                    name=f"eth{id}",
                    type=InterfaceTypeChoices.TYPE_1GE_FIXED,
                    mode=InterfaceModeChoices.MODE_TAGGED,
                )
                interface.full_clean()
                interface.save()
                interface.tags.add(vlan_sync_tag)
                self.log_debug(f"Created Interface {interface.device.name} - {interface.name}", obj=interface)
        self.log_success(f"Created {device} with {data.get('interface_count')} Interfaces")


@tag("rkt_test")
class TestAddVLANsToInterfaces(TestCase):
    def test_script(self):
        build = BuildTestDevices()
        build.run({}, True)
        class_to_test = AddVLANsToInterfaces()
        class_to_test.run({}, True)
        interfaces = Interface.objects.filter(tags__name="VLAN_TEST_SYNC_TAG")
        vlans = VLAN.objects.filter(tags__name="VLAN_TEST_SYNC_TAG")
        for i in interfaces:
            tagged_vlans = i.tagged_vlans.all()
            for v in vlans:
                self.assertTrue(v in tagged_vlans)


class AddVLANsToInterfaces(Script):
    class Meta:
        name = "2a - Add dummy VLANs to Interfaces"
        scheduling_enabled = False
        description = ""

        description = "Prod Script calculates a delta between what in on the interface and what should be on the interface"
        description += " And then adds the missing VLANs.  This script simulate worst case by adding all the VLANs to the "
        description += "interface using the loop i_obj.tagged_vlans.add(v)"
        job_timeout = 60 * 60 * 8

    # Debug Flag - will remain expose to the end user do to the complexity of the script - best to allow the user to enable it
    debug = BooleanVar(
        description="Debug Mode",
        default=str(getenv("DEBUG")).lower() == "true",
    )

    # Flag to enable debug logging
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.DEBUG = False
        self.ROCKET_IN_CIDI_TEST_ENVIRONMENT = getenv("ROCKET_IN_CIDI_TEST_ENVIRONMENT", "False").lower() == "true"

    def log_debug(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_debug(message, obj)

    def log_info(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_info(message, obj)

    def log_success(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_success(message, obj)

    def run(self, data: dict, commit: bool):
        vlan_sync_tag = "VLAN_TEST_SYNC_TAG"
        # if not self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
        #     raise AbortScript("This script can only be run in the CIDI Test Environment - PROD BLOCKED")
        if data.get("debug", False) or self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            self.DEBUG = True
        interfaces = Interface.objects.filter(tags__name=vlan_sync_tag)
        vlans = VLAN.objects.filter(tags__name=vlan_sync_tag)
        # Prod Script calculates a delta between what in on the interface and what should be on the interface
        # And then adds the missing VLANs.  This script simulate worst case by adding all the VLANs to the interface
        vlan_times = []
        interface_times = []

        for i in interfaces:
            i.snapshot()
            interface_start_time = time.time()

            for v in vlans:
                vlan_start_time = time.time()
                i.tagged_vlans.add(v)
                vlan_end_time = time.time()

                vlan_times.append(vlan_end_time - vlan_start_time)
            i.full_clean()
            i.save()
            interface_end_time = time.time()
            interface_time_delta = interface_end_time - interface_start_time
            interface_times.append(interface_time_delta)
            self.log_info(f"{i.device.name} - {i.name} took {interface_time_delta:.6f} seconds")

        # Calculate averages
        average_vlan_time = sum(vlan_times) / len(vlan_times) if vlan_times else 0
        average_interface_time = sum(interface_times) / len(interface_times) if interface_times else 0

        # Output the averages
        self.log_info(f"Average time to add a VLAN: {average_vlan_time:.6f} seconds")
        self.log_info(f"Average time to process an interface: {average_interface_time:.6f} seconds")


class AddVLANsToInterfacesBulk(Script):
    class Meta:
        name = "2b - Add dummy VLANs to Interfaces - Bulk"
        scheduling_enabled = False
        description = ""

        description = "Prod Script calculates a delta between what in on the interface and what should be on the interface"
        description += " And then adds the missing VLANs.  This script simulate worst case by adding all the VLANs to the"
        description += " interface using the i.tagged_vlans.add(*vlans_ids)"
        job_timeout = 60 * 60 * 8

    # Debug Flag - will remain expose to the end user do to the complexity of the script - best to allow the user to enable it
    debug = BooleanVar(
        description="Debug Mode",
        default=str(getenv("DEBUG")).lower() == "true",
    )

    # Flag to enable debug logging
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.DEBUG = False
        self.ROCKET_IN_CIDI_TEST_ENVIRONMENT = getenv("ROCKET_IN_CIDI_TEST_ENVIRONMENT", "False").lower() == "true"

    def log_debug(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_debug(message, obj)

    def log_info(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_info(message, obj)

    def log_success(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_success(message, obj)

    def run(self, data: dict, commit: bool):
        vlan_sync_tag = "VLAN_TEST_SYNC_TAG"
        # if not self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
        #     raise AbortScript("This script can only be run in the CIDI Test Environment - PROD BLOCKED")
        if data.get("debug", False) or self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            self.DEBUG = True
        interfaces = Interface.objects.filter(tags__name=vlan_sync_tag)
        vlans = VLAN.objects.filter(tags__name=vlan_sync_tag)
        vlans_ids = [v.id for v in vlans]
        # Prod Script calculates a delta between what in on the interface and what should be on the interface
        # And then adds the missing VLANs.  This script simulate worst case by adding all the VLANs to the interface
        vlan_times = []
        interface_times = []

        for i in interfaces:
            i.snapshot()
            interface_start_time = time.time()
            vlan_start_time = time.time()
            i.tagged_vlans.add(*vlans_ids)
            vlan_end_time = time.time()
            vlan_times.append(vlan_end_time - vlan_start_time)
            i.full_clean()
            i.save()
            interface_end_time = time.time()
            interface_time_delta = interface_end_time - interface_start_time
            interface_times.append(interface_time_delta)
            self.log_info(f"{i.device.name} - {i.name} took {interface_time_delta:.6f} seconds")

        # Calculate averages
        average_vlan_time = sum(vlan_times) / len(vlan_times) if vlan_times else 0
        average_interface_time = sum(interface_times) / len(interface_times) if interface_times else 0

        # Output the averages
        self.log_info(f"Average time to add a VLAN: {average_vlan_time:.6f} seconds")
        self.log_info(f"Average time to process an interface: {average_interface_time:.6f} seconds")


@tag("rkt_test")
class TestClearVLANFromInterfaces(TestCase):
    def test_script(self):
        build = BuildTestDevices()
        build.run({}, True)
        v_add = AddVLANsToInterfaces()
        v_add.run({}, True)
        class_to_test = ClearVLANFromTest()
        class_to_test.run({}, True)
        interfaces = Interface.objects.filter(tags__name="VLAN_TEST_SYNC_TAG")
        for i in interfaces:
            self.assertEqual(i.tagged_vlans.count(), 0)


class ClearVLANFromTest(Script):
    class Meta:
        name = "3 - Clear dummy Devices VLANs on Interfaces"
        scheduling_enabled = False
        description = "Clear all VLANs from Interfaces that were created by the test script so that the test devices can be reused"
        job_timeout = 60 * 60 * 8

    # Debug Flag - will remain expose to the end user do to the complexity of the script - best to allow the user to enable it
    debug = BooleanVar(
        description="Debug Mode",
        default=str(getenv("DEBUG")).lower() == "true",
    )

    def log_debug(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_debug(message, obj)

    def log_info(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_info(message, obj)

    def log_success(self, message, obj=None):
        if self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            return super().log_failure(message, obj)
        else:
            return super().log_success(message, obj)

    # Flag to enable debug logging
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.DEBUG = False
        self.ROCKET_IN_CIDI_TEST_ENVIRONMENT = getenv("ROCKET_IN_CIDI_TEST_ENVIRONMENT", "False").lower() == "true"

    def run(self, data: dict, commit: bool):
        vlan_sync_tag = "VLAN_TEST_SYNC_TAG"
        # if not self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
        #     raise AbortScript("This script can only be run in the CIDI Test Environment - PROD BLOCKED")
        if data.get("debug", False) or self.ROCKET_IN_CIDI_TEST_ENVIRONMENT:
            self.DEBUG = True
        interfaces = Interface.objects.filter(tags__name=vlan_sync_tag)
        for i in interfaces:
            i.snapshot()
            i.tagged_vlans.clear()
            i.full_clean()
            i.save()
            self.log_debug(f"Removed VLANs from Interface {i.device.name} - {i.name}", obj=i)
        self.log_success(f"Removed VLANs from {interfaces.count()} Interfaces")


class TestCloudConnectionsToApps(Script):
    class Meta:
        name = "4 - Test Cloud Connections to Apps"
        scheduling_enabled = False
        description = "Test Cloud Connections to Apps"
        job_timeout = 60 * 60 * 8

    testCVAAS = BooleanVar(
        description="Test CVaaS",
        default=True,
    )
    testInfoBlox = BooleanVar(
        description="Test InfoBlox",
        default=False,
    )
    testCircleCI = BooleanVar(
        description="Test CircleCI",
        default=True,
    )
    testGitHubEnterprise = BooleanVar(
        description="Test GitHub Enterprise",
        default=False,
    )
    testGitHubEMU = BooleanVar(
        description="Test GitHub EMU",
        default=True,
    )

    def run_CVaaS(self, account):
        try:
            self.log_success("Testing CVaaS Connection")
            ARISTA_CSAAS_PASSWORD = getenv(account, None)
            if ARISTA_CSAAS_PASSWORD == None:
                self.log_failure("Error os.getenv(ARISTA_CSAAS_PASSWORD) ")
                raise AbortScript("Error os.getenv(ARISTA_CSAAS_PASSWORD) ")
            API_URL = "https://www.cv-prod-us-central1-c.arista.io/api/v3/services/admin.Enrollment/AddEnrollmentToken"
            self.log_info("URL: " + str(API_URL))
            header = {"Authorization": "Bearer %s" % ARISTA_CSAAS_PASSWORD}
            data = {"enrollmentToken": {"reenrollDevices": ["*"], "validFor": "24h"}}
            self.log_info("DATA: " + str(data))
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            session = requests.Session()
            session.verify = False
            r = session.post(
                API_URL,
                json=data,
                headers=header,
                timeout=10,
            )

            self.log_info("r.status_code: " + str(r.status_code))
            self.log_info("r.text: " + str(r.text))
            self.log_info("r.headers: " + str(r.headers))
            if r.status_code == 200:
                response = r.json()[0]
                ARISTA_CSAAS_TOKEN = response["enrollmentToken"]["token"]
                ARISTA_CSAAS_TOKEN_VALID = response["enrollmentToken"]["validFor"]
                self.log_success(f"CVaaS Connection Successful - Token: ***{ARISTA_CSAAS_TOKEN[-4:]}, Valid For: {ARISTA_CSAAS_TOKEN_VALID}")
            else:
                self.log_failure(f"Error getting list: {r.text}")
                raise AbortScript("Error getting list")
        except Exception as e:
            self.log_failure(f"Error testing CVaaS Connection {type(e).__name__}: {e}")
            self.log_failure(traceback.format_exc())
            return False
        return True

    def run_Infoblox(self):
        try:
            script_ABORT = False
            INFOBLOX_VERSION = getenv("INFOBLOX_API_VERSION", "v2.7.3")
            INFOBLOX_VERIFY_CERT = str(getenv("INFOBLOX_HOST", "False")).lower() == "true"
            INFOBLOX_HOST = getenv("INFOBLOX_HOST")
            if INFOBLOX_HOST == None:
                self.log_failure("Error os.getenv(INFOBLOX_HOST) ")
                script_ABORT = True
            INFOBLOX_USERNAME = getenv("INFOBLOX_USERNAME")
            if INFOBLOX_USERNAME == None:
                self.log_failure("Error os.getenv(INFOBLOX_USERNAME) ")
                script_ABORT = True
            INFOBLOX_PASSWORD = getenv("INFOBLOX_PASSWORD")
            if INFOBLOX_PASSWORD == None:
                self.log_failure("Error os.getenv(INFOBLOX_PASSWORD) ")
                script_ABORT = True
            if script_ABORT:
                raise AbortScript("Error os.getenv(INFOBLOX_*) ")
            INFOBLOX_BASE_URL = f"https://{INFOBLOX_HOST}/wapi/{INFOBLOX_VERSION}"  # work
            self.log_success("Testing InfoBlox Connection")
            with requests.session() as s:
                grid = s.get(
                    f"{INFOBLOX_BASE_URL}/grid",
                    auth=(INFOBLOX_USERNAME, INFOBLOX_PASSWORD),
                    verify=INFOBLOX_VERIFY_CERT,
                )
                self.log_info(f"grid.status_code: {grid.status_code}")
                if grid.status_code == 200:
                    self.log_success("InfoBlox Connection Successful")
                else:
                    self.log_failure(f"Error getting grid: {grid.text}")
                    raise AbortScript("Error getting grid")
        except Exception as e:
            self.log_failure(f"Error testing InfoBlox Connection {type(e).__name__}: {e}")
            self.log_failure(traceback.format_exc())
            return False
        return True

    def run_CircleCI(self):
        try:
            session = requests.Session()
            session.verify = False
            CIRCLECI_API_URL = getenv("CIRCLECI_API_URL", "/api/v2/project/github/")
            CIRCLECI_HOST = getenv("CIRCLECI_HOST", "")
            CIRCLECI_TOKEN = getenv("CIRCLECI_TOKEN", "")
            if CIRCLECI_API_URL == "":
                raise AbortScript("Missing CIRCLECI_API_URL")
            if CIRCLECI_HOST == "":
                raise AbortScript("Missing CIRCLECI_HOST")
            if CIRCLECI_TOKEN == "":
                raise AbortScript("Missing CIRCLECI_TOKEN")
            base_url = f"https://{CIRCLECI_HOST}{CIRCLECI_API_URL}"
            url = f"{base_url}networkteam/DCN-IAC/pipeline"  # TEST
            headers = {"Circle-Token": CIRCLECI_TOKEN, "Content-Type": "application/json"}
            payload = {
                "parameters": {
                    "run_device_modified": True,
                    "netbox_pipeline": "DC",
                    "devices_name": "",
                    "change_request_number": "TEST-DELETE-ME",
                }
            }
            self.log_info(str(f"URL: {url}"))
            self.log_info(f"payload: {payload}\n")
            r = session.post(url, json=payload, headers=headers, verify=False, timeout=10)

            if r.status_code == 200 or r.status_code == 201:
                response = r.json()
                self.log_success(f"CI has been triggered {response})")  # 201 indicates OK
            else:
                self.log_failure(f"Error calling CI:  Code: {r.status_code} - response: {r.text}")
                raise AbortScript("Error creating fixed address")

        except Exception as e:
            self.log_failure(f"Error testing CircleCI Connection {type(e).__name__}: {e}")
            self.log_failure(traceback.format_exc())
            return False
        return True

    def github_test(self, url, GITHUB_AUTHORIZATION):
        try:
            self.log_info("Attempting Post to CircleCI - Data Center")

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            session = requests.Session()
            session.verify = False

            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {GITHUB_AUTHORIZATION}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            parameters = {
                # "run_device_modified": True,
                # "netbox_pipeline": netbox_pipeline,
                "devices_name": "",
                "change_request_number": "",
            }

            payload = {
                "ref": "main",
                "inputs": parameters,
            }
            self.log_info(str(f"URL: {url}"))
            self.log_info(f"payload: {payload}\n")

            r = session.post(url, json=payload, headers=headers, verify=False)

            if r.status_code == 200 or r.status_code == 201 or r.status_code == 204:
                # response = r.json()
                self.log_success(f"CI has been triggered {r.text})")  # 201 indicates OK
            else:
                self.log_failure(f"Error calling CI:  Code: {r.status_code} - response: {r.text}")
                raise AbortScript("Error creating fixed address")

        except Exception as e:
            self.log_failure(f"Error testing GitHub Connection {type(e).__name__}: {e}")
            self.log_failure(traceback.format_exc())
            return False
        return True

    def run_GitHubEnterprise(self):
        self.log_info("Testing GitHub Enterprise Connection")
        self.log_info("GitHub Enterprise Connection Test is not implemented yet")
        return False

    def run_GitHubEMU(self):
        url = "https://api.github.com/repos/rocketcentral/network-dcn-iac/actions/workflows/build_config.yml/dispatches"
        GITHUB_AUTHORIZATION = getenv("GITHUB_AUTHORIZATION", None)
        if GITHUB_AUTHORIZATION is None:
            self.log_failure("Error os.getenv(GITHUB_AUTHORIZATION) ")
            return False
        return self.github_test(url, GITHUB_AUTHORIZATION)

    def run(self, data: dict, commit: bool):
        self.log_info("Testing Cloud Connections to Apps")
        status_report = "Cloud Connections to Apps Test Report:\n"
        if data.get("testCVAAS", False):
            accounts = ("ARISTA_CSAAS_PASSWORD", "ARISTA_CVAAS_DC_PASSWORD", "ARISTA_CVAAS_CAMPUS_PASSWORD", "ARISTA_CVAAS_LEGACY_PASSWORD")
            self.log_info(f"Testing CVaaS for accounts: ")
            for account in accounts:

                if self.run_CVaaS(account):
                    status_report += f"   {account}: SUCCESS\n"
                else:
                    status_report += f"   {account}: FAILED\n"
        else:
            status_report += "CVaaS Connection Test: SKIPPED\n"
        if data.get("testInfoBlox", False):
            if self.run_Infoblox():
                status_report += "InfoBlox Connection Test: SUCCESS\n"
            else:
                status_report += "InfoBlox Connection Test: FAILED\n"
        else:
            status_report += "InfoBlox Connection Test: SKIPPED\n"
        if data.get("testCircleCI", False):

            if self.run_CircleCI():
                status_report += f"CircleCI Connection Test: SUCCESS\n"
            else:
                status_report += f"CircleCI Connection Test: FAILED\n"
        else:
            status_report += "CircleCI Connection Test: SKIPPED\n"
        if data.get("testGitHubEnterprise", False):
            if self.run_GitHubEnterprise():
                status_report += "GitHub Enterprise Connection Test: SUCCESS\n"
            else:
                status_report += "GitHub Enterprise Connection Test: FAILED\n"
        else:
            status_report += "GitHub Enterprise Connection Test: SKIPPED\n"
        if data.get("testGitHubEMU", False):
            if self.run_GitHubEMU():
                status_report += "GitHub EMU Connection Test: SUCCESS\n"
            else:
                status_report += "GitHub EMU Connection Test: FAILED\n"
        else:
            status_report += "GitHub EMU Connection Test: SKIPPED\n"
        self.log_info(status_report)
        self.log_success("Cloud Connections to Apps Test Completed Successfully")
        return status_report


def get_environment(text=True):
    hidden = ("TOKEN", "PASSWORD", "SECRET", "KEY", "AUTHORIZATION", "SECRET", "SHA265", "SEED")
    environ_items = os.environ.items()
    # Sort environment variables by key
    return_data = []
    environ_items = sorted(environ_items, key=lambda x: x[0].upper())

    for key, value in environ_items:
        if any(hidden_word in key.upper() for hidden_word in hidden):
            value = "*" * (len(value) - 3) + value[-3:]  # Mask the value but show the last 4 characters
        return_data.append(f"{key}: {value}")
    if text:
        return "\n".join(return_data)
    else:
        return return_data


class GetEnvironmentVariables(Script):
    class Meta:
        name = "5 - Get Environment Variables"
        scheduling_enabled = False
        description = "Get Environment Variables for the current environment"

    text = TextVar(
        description="WebGUI",
        default=get_environment(text=True),
    )

    def run(self, data: dict, commit: bool):
        self.log_info("RQWorker Environment Variables:")
        for line in get_environment(text=False):
            self.log_info(line)
        self.log_success("Environment Variables Retrieved Successfully")
        return get_environment(text=True)


script_order = (
    BuildTestDevices,
    AddVLANsToInterfaces,
    AddVLANsToInterfacesBulk,
    ClearVLANFromTest,
    TestCloudConnectionsToApps,
    GetEnvironmentVariables,
)
