import json, os, subprocess, logging, csv, asyncio
from collections import defaultdict

os.environ['AWS_PAGER'] = ''
logging.basicConfig(filename='log.log', filemode='w', level=logging.INFO)

new_A_1 = '10.0.10.2'
new_A_2 = '10.0.10.1'
new_CNAME = 'proxy.cname.com'

aws_profile = 'route53'

updated_zones = []
skipped_zones = []

input_file = 'filtered_records.csv'
records = defaultdict(dict)
zone_id_to_domains = defaultdict(set)


with open(input_file, 'r') as infile:
    reader = csv.DictReader(infile)
    for row in reader:
        zone_id = row['zone_id'].strip()
        domain_name = row['name'].strip()

        key_A = (zone_id, domain_name)
        key_CNAME = (zone_id, f"www.{domain_name.rstrip('.')}.")  # add trailing dot

        records[key_A]['A'] = True
        records[key_CNAME]['CNAME'] = True
        zone_id_to_domains[zone_id].add(domain_name)

zone_changes = defaultdict(list)

for (zone_id, name), types in records.items():
    if 'A' in types:
        zone_changes[zone_id].append({
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": name,
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [
                    {"Value": new_A_1},
                    {"Value": new_A_2}
                ]
            }
        })

    if 'CNAME' in types:
        zone_changes[zone_id].append({
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": name,
                "Type": "CNAME",
                "TTL": 300,
                "ResourceRecords": [
                    {"Value": new_CNAME}
                ]
            }
        })


for zone_id, changes in zone_changes.items():
    change_batch = {
        "Comment": "Point A and CNAME records to WP Engine",
        "Changes": changes
    }

    filename = f'changes_{zone_id.strip("/")}.json'
    with open(filename, 'w') as f:
        json.dump(change_batch, f, indent=4)

    print(f"\033[91m\n----- Current configuration for {zone_id} -----\033[0m\nShowing current A and CNAME record, if found")
    cmd = f"aws route53 list-resource-record-sets --hosted-zone-id {zone_id} --no-cli-pager --profile {aws_profile}"
    result_current = subprocess.check_output(cmd, shell=True, text=True)
    current_record_data = json.loads(result_current)

    for change in changes:
        name = change['ResourceRecordSet']['Name'].strip('.')

        # Derive domain name (remove www. if present)
        domain_name = name[len('www.'):] if name.startswith('www.') else name

        root_domain = domain_name
        www_domain = f"www.{root_domain}"

        matched_records = [
            record for record in current_record_data['ResourceRecordSets']
            if (
                (record['Type'] == 'A' and record['Name'].strip('.') == root_domain) or
                (record['Type'] == 'CNAME' and record['Name'].strip('.') == www_domain)
            )
        ]

    for rec in matched_records:
        print(json.dumps(rec, indent=4))
    print(f"\033[91m\n----- Changes for zone {zone_id} -----\033[0m")
    print(json.dumps(change_batch, indent=4))
    confirm = input("Do you want to apply these changes? (Y/n): ").strip().lower()

    if confirm == 'y':
        try:
            cmd = f"aws route53 change-resource-record-sets --hosted-zone-id {zone_id} --change-batch file://{filename} --no-cli-pager --profile {aws_profile}"
            result = subprocess.check_output(cmd, shell=True, text=True)
            print(f"Applied changes to {zone_id}:\n{result}")
            updated_zones.append(zone_id)
        except subprocess.CalledProcessError as e:
            print(f"Error applying changes to {zone_id}: {e}")
            logging.error(f"Error applying changes to {zone_id}: {e}")
            skipped_zones.append(zone_id)
    else:
        print(f"\033[93mSkipped applying changes to {zone_id}\033[0m")
        skipped_zones.append(zone_id)

        try:
            cmd = f"aws route53 list-resource-record-sets --hosted-zone-id {zone_id} --no-cli-pager --profile {aws_profile}"
            result = subprocess.check_output(cmd, shell=True, text=True)
            record_data = json.loads(result)

            print(f"\n\033[94mCurrent A and CNAME records in zone {zone_id}:\033[0m")

            for change in changes:
                name = change['ResourceRecordSet']['Name'].strip('.')
                type_ = change['ResourceRecordSet']['Type']

                matched_records = [
                    record for record in record_data['ResourceRecordSets']
                    if record['Type'] == type_ and record['Name'].strip('.') == name
                ]

                for rec in matched_records:
                    print(json.dumps(rec, indent=4))

        except subprocess.CalledProcessError as e:
            print(f"\033[91mError listing current records for {zone_id}: {e}\033[0m")


print(f"\033[92mUpdated zones ({len(updated_zones)}):\033[0m")
for i in updated_zones:
    domains = ', '.join(sorted(zone_id_to_domains[i]))
    print(f"  - {i} ({domains})")

print(f"\033[93mSkipped zones ({len(skipped_zones)}):\033[0m")
for i in skipped_zones:
    domains = ', '.join(sorted(zone_id_to_domains[i]))
    print(f"  - {i} ({domains})")