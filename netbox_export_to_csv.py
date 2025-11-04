import argparse
import csv
import pynetbox

# Only imported if --xlsx is used
try:
    import xlsxwriter  # pip install xlsxwriter
except Exception:
    xlsxwriter = None

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
    elif object_type in ["ip_addresses", "ip_address", "ipaddresses"]:
        return nb.ipam.ip_addresses
    elif object_type in ["prefixes", "prefix"]:
        return nb.ipam.prefixes
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
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("label") or value.get("value") or ""
    return str(value)

def _maybe_name(obj):
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

def _write_csv(path, fieldnames, rows):
    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def _write_xlsx_sheet(ws, fieldnames, rows):
    # write header
    for col, h in enumerate(fieldnames):
        ws.write(0, col, h)
    # write rows
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, h in enumerate(fieldnames):
            ws.write(r_idx, c_idx, row.get(h, ""))

def export_netbox_to_csv(url, token, object_types, xlsx_path=None):
    nb = pynetbox.api(url, token=token)

    # If building an xlsx, collect per-object-type rows & headers
    xlsx_data = {}  # obj_type -> (fieldnames, rows)

    for obj_type in object_types:
        endpoint = get_endpoint(nb, obj_type)
        if endpoint is None:
            print(f"Unknown object type: {obj_type}. Skipping.")
            continue

        try:
            records = list(endpoint.all())
        except Exception as e:
            print(f"Failed to fetch {obj_type}: {e}")
            continue

        csv_filename = f"{obj_type}.csv"

        # Devices (custom flattened)
        if obj_type.lower() in ["devices", "device"]:
            fieldnames = [
                "id", "name", "role", "device_type", "manufacturer",
                "site", "location", "rack", "rack_face", "position", "status",
                "tenant", "platform", "serial", "asset_tag",
                "primary_ip4", "primary_ip6", "tags"
            ]
            rows = []
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
                devtype = getattr(device, "device_type", None)
                if devtype:
                    row["device_type"] = _maybe_name(devtype)
                    try:
                        row["manufacturer"] = _maybe_name(getattr(devtype, "manufacturer", None))
                    except Exception:
                        row["manufacturer"] = ""

                ip4 = getattr(device, "primary_ip4", None)
                ip6 = getattr(device, "primary_ip6", None)
                row["primary_ip4"] = getattr(ip4, "address", str(ip4)) if ip4 else ""
                row["primary_ip6"] = getattr(ip6, "address", str(ip6)) if ip6 else ""

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

                rows.append(row)

            _write_csv(csv_filename, fieldnames, rows)
            print(f"Exported {len(rows)} devices to {csv_filename}")
            if xlsx_path:
                xlsx_data[obj_type] = (fieldnames, rows)

        # Cables (custom flattened)
        elif obj_type.lower() in ["cables", "cable"]:
            fieldnames = [
                "id",
                "termination_a_device", "termination_a_name",
                "termination_b_device", "termination_b_name",
                "status", "label"
            ]
            rows = []
            for cable in records:
                try:
                    term_a = getattr(cable, "termination_a", None)
                    device_a = _maybe_name(getattr(term_a, "device", None))
                    name_a = _maybe_name(getattr(term_a, "name", None)) if hasattr(term_a, "name") else _maybe_name(term_a)
                except Exception:
                    device_a, name_a = "", ""

                try:
                    term_b = getattr(cable, "termination_b", None)
                    device_b = _maybe_name(getattr(term_b, "device", None))
                    name_b = _maybe_name(getattr(term_b, "name", None)) if hasattr(term_b, "name") else _maybe_name(term_b)
                except Exception:
                    device_b, name_b = "", ""

                rows.append({
                    "id": cable.id,
                    "termination_a_device": device_a,
                    "termination_a_name": name_a,
                    "termination_b_device": device_b,
                    "termination_b_name": name_b,
                    "status": _choice_to_label(getattr(cable, "status", None)),
                    "label": getattr(cable, "label", "") or ""
                })

            _write_csv(csv_filename, fieldnames, rows)
            print(f"Exported {len(rows)} cables to {csv_filename}")
            if xlsx_path:
                xlsx_data[obj_type] = (fieldnames, rows)

        # Generic (serialize & flatten)
        else:
            rows = []
            fieldnames = None
            serialized = []
            for rec in records:
                data = rec.serialize()
                serialized.append(data)

            # build headers
            all_fields = set()
            for d in serialized:
                all_fields.update(d.keys())
            fieldnames = sorted(all_fields)
            if "id" in fieldnames:
                fieldnames.remove("id"); fieldnames.insert(0, "id")
            if "name" in fieldnames:
                fieldnames.remove("name"); fieldnames.insert(1, "name")
            elif "address" in fieldnames:
                fieldnames.remove("address"); fieldnames.insert(1, "address")

            # flatten rows
            for item in serialized:
                flat = {}
                for k, v in item.items():
                    if v is None:
                        flat[k] = ""
                    elif isinstance(v, dict):
                        flat[k] = v.get("label") or v.get("value") or v.get("name") or str(v)
                    elif hasattr(v, "__iter__") and not isinstance(v, str):
                        try:
                            flat[k] = ",".join(
                                (vv.get("name") if isinstance(vv, dict) and "name" in vv
                                 else (vv.name if hasattr(vv, "name") else str(vv)))
                                for vv in v
                            )
                        except Exception:
                            flat[k] = ",".join(str(vv) for vv in v)
                    else:
                        flat[k] = str(v)
                rows.append(flat)

            _write_csv(csv_filename, fieldnames, rows)
            print(f"Exported {len(rows)} {obj_type} to {csv_filename}")
            if xlsx_path:
                xlsx_data[obj_type] = (fieldnames, rows)

    # If requested, build a single XLSX with one sheet per object type
    if xlsx_path:
        if xlsxwriter is None:
            raise RuntimeError("xlsxwriter is not installed. Run: pip install xlsxwriter")
        wb = xlsxwriter.Workbook(xlsx_path)
        try:
            for obj_type, (headers, rows) in xlsx_data.items():
                # Excel sheet names max 31 chars; sanitize a bit
                sheet_name = obj_type[:31]
                ws = wb.add_worksheet(sheet_name)
                _write_xlsx_sheet(ws, headers, rows)
        finally:
            wb.close()
        print(f"Wrote Excel workbook: {xlsx_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export NetBox objects to CSV (and optional XLSX).")
    parser.add_argument("--url", required=True, help="Base URL of NetBox (e.g. https://netbox.example.com)")
    parser.add_argument("--token", required=True, help="API token for NetBox")
    parser.add_argument("--objects", nargs='+', required=True, help="One or more object types to export (space-separated)")
    parser.add_argument("--xlsx", help="Optional path to write a single Excel workbook with one sheet per object type")
    args = parser.parse_args()
    export_netbox_to_csv(args.url, args.token, args.objects, xlsx_path=args.xlsx)
