import argparse
import csv
import pynetbox

# Map object type names to pynetbox endpoints
def get_endpoint(nb, object_type):
    object_type = object_type.lower()
    if object_type in ["devices", "device"]:
        return nb.dcim.devices
    elif object_type in ["device_types", "device_type"]:
        return nb.dcim.device_types
    elif object_type in ["roles", "role"]:
        return nb.dcim.roles
    elif object_type in ["interfaces", "interface"]:
        return nb.dcim.interfaces
    elif object_type in ["cables", "cable"]:
        return nb.dcim.cables
    elif object_type in ["sites", "site"]:
        return nb.dcim.sites
    elif object_type in ["racks", "rack"]:
        return nb.dcim.racks
    elif object_type in ["manufacturers", "manufacturer"]:
        return nb.dcim.manufacturers
    # ... (additional mappings for other object types)
    elif object_type in ["ip_addresses", "ip_address", "ipaddresses"]:
        return nb.ipam.ip_addresses
    elif object_type in ["prefixes", "prefix"]:
        return nb.ipam.prefixes
    # ... (include other apps like tenancy, circuits, virtualization as needed)
    elif object_type in ["tenants", "tenant"]:
        return nb.tenancy.tenants
    elif object_type in ["circuits", "circuit"]:
        return nb.circuits.circuits
    elif object_type in ["providers", "provider"]:
        return nb.circuits.providers
    elif object_type in ["virtual_machines", "virtual_machine", "vm", "vms"]:
        return nb.virtualization.virtual_machines
    else:
        return None

def _choice_to_label(value):
    """NetBox 4.x generally returns choice fields as strings; older clients may have dicts with labels."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("label") or value.get("value") or ""
    return str(value)

def _maybe_name(obj):
    """Return a name/label if present, else string-cast, else empty."""
    if obj is None:
        return ""
    for attr in ("name", "label", "model"):
        if hasattr(obj, attr):
            try:
                val = getattr(obj, attr)
                if val:
                    return str(val)
            except Exception:
                pass
    return str(obj)

def export_netbox_to_csv(url, token, object_types):
    # Initialize NetBox API connection
    nb = pynetbox.api(url, token=token)

    for obj_type in object_types:
        endpoint = get_endpoint(nb, obj_type)
        if endpoint is None:
            print(f"Unknown object type: {obj_type}. Skipping.")
            continue

        # Retrieve all records for the given object type
        try:
            records = list(endpoint.all())  # fetches all objects (handles pagination)
        except Exception as e:
            print(f"Failed to fetch {obj_type}: {e}")
            continue

        csv_filename = f"{obj_type}.csv"

        # Special handling for devices
        if obj_type.lower() in ["devices", "device"]:
            with open(csv_filename, mode='w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    "id", "name", "role", "device_type", "manufacturer",
                    "site", "location", "rack", "rack_face", "position", "status",
                    "tenant", "platform", "serial", "asset_tag",
                    "primary_ip4", "primary_ip6", "tags"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for device in records:
                    row = {
                        "id": device.id,
                        "name": device.name,
                        "role": _maybe_name(getattr(device, "role", None)),
                        "device_type": "",
                        "manufacturer": "",
                        "site": _maybe_name(getattr(device, "site", None)),
                        "location": _maybe_name(getattr(device, "location", None)),
                        "rack": _maybe_name(getattr(device, "rack", None)),
                        "rack_face": _choice_to_label(getattr(device, "face", None)),
                        "position": getattr(device, "position", "") or "",
                        "status": _choice_to_label(getattr(device, "status", None)),
                        "tenant": _maybe_name(getattr(device, "tenant", None)),
                        "platform": _maybe_name(getattr(device, "platform", None)),
                        "serial": getattr(device, "serial", "") or "",
                        "asset_tag": getattr(device, "asset_tag", "") or "",
                        "primary_ip4": "",
                        "primary_ip6": "",
                        "tags": ""
                    }
                    # Device type & manufacturer
                    devtype = getattr(device, "device_type", None)
                    if devtype:
                        row["device_type"] = _maybe_name(devtype)
                        try:
                            row["manufacturer"] = _maybe_name(getattr(devtype, "manufacturer", None))
                        except Exception:
                            row["manufacturer"] = ""

                    # Primary IPs (object or string)
                    ip4 = getattr(device, "primary_ip4", None)
                    ip6 = getattr(device, "primary_ip6", None)
                    row["primary_ip4"] = getattr(ip4, "address", str(ip4)) if ip4 else ""
                    row["primary_ip6"] = getattr(ip6, "address", str(ip6)) if ip6 else ""

                    # Tags (list or string)
                    tags = getattr(device, "tags", None)
                    if isinstance(tags, list):
                        try:
                            row["tags"] = ",".join(
                                t.get("name") if isinstance(t, dict) and "name" in t
                                else (t.name if hasattr(t, "name") else str(t))
                                for t in tags
                            )
                        except Exception:
                            row["tags"] = ",".join(str(t) for t in tags)
                    elif tags:
                        row["tags"] = str(tags)

                    writer.writerow(row)
            print(f"Exported {len(records)} devices to {csv_filename}")

        # Special handling for cables
        elif obj_type.lower() in ["cables", "cable"]:
            with open(csv_filename, mode='w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    "id",
                    "termination_a_device", "termination_a_name",
                    "termination_b_device", "termination_b_name",
                    "status", "label"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for cable in records:
                    # End A
                    try:
                        term_a = getattr(cable, "termination_a", None)
                        device_a = _maybe_name(getattr(term_a, "device", None))
                        name_a = _maybe_name(getattr(term_a, "name", None)) if hasattr(term_a, "name") else _maybe_name(term_a)
                    except Exception:
                        device_a, name_a = "", ""
                    # End B
                    try:
                        term_b = getattr(cable, "termination_b", None)
                        device_b = _maybe_name(getattr(term_b, "device", None))
                        name_b = _maybe_name(getattr(term_b, "name", None)) if hasattr(term_b, "name") else _maybe_name(term_b)
                    except Exception:
                        device_b, name_b = "", ""
                    status_label = _choice_to_label(getattr(cable, "status", None))
                    label = getattr(cable, "label", "") or ""
                    writer.writerow({
                        "id": cable.id,
                        "termination_a_device": device_a,
                        "termination_a_name": name_a,
                        "termination_b_device": device_b,
                        "termination_b_name": name_b,
                        "status": status_label,
                        "label": label
                    })
            print(f"Exported {len(records)} cables to {csv_filename}")

        # Generic handling for other object types
        else:
            with open(csv_filename, mode='w', newline='', encoding='utf-8') as f:
                if not records:
                    writer = csv.writer(f)
                    writer.writerow([])  # empty header for no data
                else:
                    # Determine all field names present in this object type
                    all_fields = set()
                    serialized_data = []
                    for rec in records:
                        data = rec.serialize()  # convert Record to dict of fields
                        serialized_data.append(data)
                        all_fields.update(data.keys())
                    fieldnames = sorted(all_fields)
                    if 'id' in fieldnames:
                        fieldnames.remove('id'); fieldnames.insert(0, 'id')
                    if 'name' in fieldnames:
                        fieldnames.remove('name'); fieldnames.insert(1, 'name')
                    elif 'address' in fieldnames:  # e.g., IP addresses or prefixes
                        fieldnames.remove('address'); fieldnames.insert(1, 'address')

                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for item in serialized_data:
                        # Flatten nested structures for readability
                        flat = {}
                        for key, value in item.items():
                            if value is None:
                                flat[key] = ""
                            elif isinstance(value, dict):
                                flat[key] = value.get('label') or value.get('value') or value.get('name') or str(value)
                            elif hasattr(value, '__iter__') and not isinstance(value, str):
                                try:
                                    flat[key] = ",".join(
                                        str(v.get('name')) if isinstance(v, dict) and 'name' in v
                                        else (v.name if hasattr(v, 'name') else str(v))
                                        for v in value
                                    )
                                except Exception:
                                    flat[key] = ",".join(str(v) for v in value)
                            else:
                                # For Record objects or other types, string-cast
                                flat[key] = str(value)
                        writer.writerow(flat)
            print(f"Exported {len(records)} {obj_type} to {csv_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export NetBox objects to CSV.")
    parser.add_argument("--url", required=True, help="Base URL of NetBox (e.g. https://netbox.example.com)")
    parser.add_argument("--token", required=True, help="API token for NetBox")
    parser.add_argument("--objects", nargs='+', required=True, help="One or more object types to export (space-separated)")
    args = parser.parse_args()
    export_netbox_to_csv(args.url, args.token, args.objects)
