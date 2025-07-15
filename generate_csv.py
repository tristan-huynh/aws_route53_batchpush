import json, os, subprocess, logging, csv

os.environ['AWS_PAGER'] = ''
logging.basicConfig(filename='log.log', filemode='w', level=logging.INFO)

aws_profile = 'route53'

os.system(f'aws route53 list-hosted-zones > routes.json --no-cli-pager --profile {aws_profile}')

# Open file 
with open('routes.json', 'r') as file:
    data = json.load(file)

with open('filtered_records.csv', 'w', newline='') as csvfile:
    fieldnames = ['zone_id', 'name', 'type', 'value']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for i in data['HostedZones']:
        zone_id = i['Id']
        zone_name = i['Name'] 
        cmd = f"aws route53 list-resource-record-sets --hosted-zone-id {zone_id} --no-cli-pager --profile {aws_profile}"
        try:
            result = subprocess.check_output(cmd, shell=True, text=True)
            record_data = json.loads(result)

            # Filter for only A and CNAME records
            filtered_records = [
                record for record in record_data['ResourceRecordSets']
                if (record['Type'] == 'A' and record['Name'] == zone_name) or (record['Type'] == 'CNAME' and record['Name'].startswith('www'))
            ]

            for record in filtered_records:
                name = record['Name']
                record_type = record['Type']
                values = ",".join([r['Value'] for r in record.get('ResourceRecords', [])])
                writer.writerow({
                    'zone_id': zone_id,
                    'name': name,
                    'type': record_type,
                    'value': values
                })
            print(f"Filtered {len(filtered_records)} records from {zone_id}")

            if len(filtered_records) != 2:
                logging.info(f"Filtered {len(filtered_records)} records from {zone_id}")

        except subprocess.CalledProcessError as e:
            logging.error(f'{zone_id}: {e}')
