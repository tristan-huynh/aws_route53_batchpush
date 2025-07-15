import json, os, subprocess, logging, csv

os.environ['AWS_PAGER'] = ''
logging.basicConfig(filename='log.log', filemode='w', level=logging.INFO)


with open('better_filtered_records.csv', 'r') as csvfile:
    fieldnames = ['zone_id', 'name', 'type', 'value']
    reader = csv.DictReader(csvfile, fieldnames=fieldnames)

    for i in reader:
        zone_id = i['zone_id']
        name = i['name']
        # type_ = i['type']   
        # value = i['value']

        # if type_ == 'CNAME':
        tld = name
        cmd = f"nslookup {tld} 8.8.8.8"
        try:
            result = subprocess.check_output(cmd, shell=True, text=True)
            with open('verification.txt', 'a') as f:
                f.write(f"nslookup {tld.strip('.')}\n{result}\n\n")
        except subprocess.CalledProcessError as e:
            logging.error(f'{tld} : {e}')