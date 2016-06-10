import json
import boto3
import base64
import uuid
from datetime import datetime
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

print('Loading function ' + datetime.now().time().isoformat())
route53 = boto3.client('route53')
ec2 = boto3.resource('ec2')
compute = boto3.client('ec2')
dynamodb_client = boto3.client('dynamodb')
dynamodb_resource = boto3.resource('dynamodb')

def lambda_handler(event, context):
	""" Check to see whether a DynamoDB table already exists.  If not, create it.  This table is used to keep a record of
	instances that have been created along with their attributes.  This is necessary because when you terminate an instance
	its attributes are no longer available, so they have to be fetched from the table."""
	tables = dynamodb_client.list_tables()

	if 'DDNS' in tables['TableNames']:
		print 'DynamoDB table already exists'
	else:
		create_table('DDNS')

	# Set variables
	# Get the state from the Event stream
	state = event['detail']['state']
	# Get the instance id, region, and tag collection
	logger.info(event['detail'])
	instance_id = event['detail']['instance-id']
	table = dynamodb_resource.Table('DDNS')


	instance = compute.describe_instances(InstanceIds=[instance_id])
	ipaddress = instance['Reservations'][0]['Instances'][0]['PrivateIpAddress']
	host_name = ''
	domain = ''
	aliases = None

	instanceDb = table.get_item(
		Key={
			'InstanceId': instance_id
		},
		AttributesToGet=[
			'Hostname',
			'Domain',
			'IpAddress',
			'Aliases'
			]
	)

	instanceDb.pop('ResponseMetadata')

	userData = compute.describe_instance_attribute(InstanceId=instance_id,Attribute='userData')
	
	if 'UserData' in userData and 'Value' in userData['UserData']:
		udJson = json.loads(base64.b64decode(userData['UserData']['Value']))
		host_name = udJson['hostname']
		domain = udJson['domainname']
		if 'aliases' in udJson:
			aliases = udJson['aliases']

	if 'Item' in instanceDb:
		if not domain:
			domain=instanceDb['Item']['Domain']
		if not host_name:
			host_name=instanceDb['Item']['Hostname']
		#ipaddress=instanceDb['Item']['IpAddress']
		if aliases is None:
			if 'Aliases' in instanceDb['Item']:
				aliases = instanceDb['Item']['Aliases']

	if aliases is None:
		table.put_item(
			Item = {
				'InstanceId': instance_id,
				'Hostname': host_name,
				'Domain': domain,
				'IpAddress': ipaddress
			}
		)
	else:
		table.put_item(
			Item = {
				'InstanceId': instance_id,
				'Hostname': host_name,
				'Domain': domain,
				'IpAddress': ipaddress,
				'Aliases': aliases
			}
		)

	zoneid = get_zone_id(domain)

	if zoneid is None:
		vpcid = instance['Reservations'][0]['Instances'][0]['VpcId']
		region = event['region']
		create_hosted_zone(vpcid, domain, region)
		zoneid = get_zone_id(domain)

	if state == 'running':
		create_resource_record(zoneid, host_name+'.'+domain+'.', 'A', ipaddress)
		if aliases is not None:
			for alias in aliases:
				create_resource_record(zoneid, alias+'.'+domain+'.', 'CNAME', host_name+'.'+domain)
	elif state == 'stopped' or state == 'shutting-down':
		try:
			delete_resource_record(zoneid, host_name+'.'+domain+'.', 'A', ipaddress)
			if aliases is not None:
				for alias in aliases:
					delete_resource_record(zoneid, alias+'.'+domain+'.', 'CNAME', host_name+'.'+domain)
		except BaseException as e:
			logger.error(e)
		if state == 'shutting-down':
			table.delete_item(
				Key={
					'InstanceId': instance_id
				}
			)

def create_table(table_name):
    dynamodb_client.create_table(
            TableName=table_name,
            AttributeDefinitions=[
                {
                    'AttributeName': 'InstanceId',
                    'AttributeType': 'S'
                },
            ],
            KeySchema=[
                {
                    'AttributeName': 'InstanceId',
                    'KeyType': 'HASH'
                },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 4,
                'WriteCapacityUnits': 4
            }
        )
    table = dynamodb_resource.Table(table_name)
    table.wait_until_exists()

def create_resource_record(zone_id, name, type, value):
    """This function creates resource records in the hosted zone passed by the calling function."""
    print 'Updating %s record %s with %s ' % (type, name, value)
    route53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    "Comment": "Updated by Lambda DDNS",
                    "Changes": [
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Name": name,
                                "Type": type,
                                "TTL": 60,
                                "ResourceRecords": [
                                    {
                                        "Value": value
                                    },
                                ]
                            }
                        },
                    ]
                }
            )

def delete_resource_record(zone_id, name, type, value):
    """This function deletes resource records from the hosted zone passed by the calling function."""
    print 'Deleting %s record %s with %s' % (type, name, value)
    route53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    "Comment": "Updated by Lambda DDNS",
                    "Changes": [
                        {
                            "Action": "DELETE",
                            "ResourceRecordSet": {
                                "Name": name,
                                "Type": type,
                                "TTL": 60,
                                "ResourceRecords": [
                                    {
                                        "Value": value
                                    },
                                ]
                            }
                        },
                    ]
                }
            )

def get_zone_id(zone_name):
    """This function returns the zone id for the zone name that's passed into the function."""
    if zone_name[-1] != '.':
        zone_name = zone_name + '.'
    hosted_zones = route53.list_hosted_zones()
    x = filter(lambda record: record['Name'] == zone_name, hosted_zones['HostedZones'])
    try:
        zone_id_long = x[0]['Id']
        zone_id = str.split(str(zone_id_long),'/')[2]
        return zone_id
    except:
        return None

def create_hosted_zone(vpcid, domain, region):
	"""Creates the reverse lookup zone."""
	print 'Creating hosted zone %s' % domain + '.'
	route53.create_hosted_zone(
		Name = domain + '.',
		VPC = {
			'VPCRegion':region,
			'VPCId': vpcid
		},
		CallerReference=str(uuid.uuid1()),
		HostedZoneConfig={
			'Comment': 'Updated by Lambda DDNS',
		},
	)
