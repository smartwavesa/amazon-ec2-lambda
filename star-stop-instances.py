import boto3
from datetime import datetime, date, time
from dateutil import tz
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def getInstancesFromTags(tagKey,tagValue,state):
	client = boto3.client('ec2')
	instDict=client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': [state]},{'Name': 'tag:'+tagKey, 'Values': [tagValue]}])
	instances=[]
	for r in instDict['Reservations']:
		for inst in r['Instances']:
			instances.append(inst)
	return instances
	
def buildMessageForSQS(action,instances):
	message = "{"
	message = message + "'Action': '"+action+"',"
	message = message + "'instances' : "+str(instances)+ "}"
	logger.info(message)
	sendToSQS(message)

def sendToSQS(message):
	client = boto3.client('sqs')
	response = client.send_message(
	QueueUrl='https://sqs.eu-west-1.amazonaws.com/648292630089/sw-aws-scheduled-instances',
	MessageBody= message
)

def handler(event, context):
	startHour=8
	stopHour=20
	dyna = boto3.client('dynamodb')
	dbresponse = dyna.scan(
		TableName='office_hours',
		Select='ALL_ATTRIBUTES'
	)
	for name in dbresponse['Items']:
		if name['name']['S']=='start':
			startHour=int(name['time']['N'])
		elif name['name']['S']=='stop':
			stopHour=int(name['time']['N'])
	client = boto3.client('ec2')
	stopped='stopped'
	running='running'
	tagKey = 'Schedule'
	tagValue='office_hours'
	if 'tagValue' in event:
		tagValue = event['tagValue']
	
	parisTimeZone = tz.gettz('Europe/Paris')
	nowDate=datetime.now(parisTimeZone)
	
	currentHour = int(nowDate.hour)
	officeHours=False
	if currentHour >= startHour and currentHour < stopHour and int(nowDate.weekday())<5:
		officeHours=True
	
	instancesToStart=[]
	instancesToStop=[]
	
	if officeHours:
		instancesToStart.extend(getInstancesFromTags('Schedule','office_hours',stopped))
	else:
		instancesToStop.extend(getInstancesFromTags('Schedule','office_hours',running))
	
	instancesToStart.extend(getInstancesFromTags('Schedule','always',stopped))
	
	if not instancesToStart:
		logger.info('No instances to start!')
	else:
		hostIds=[]
		for inst in instancesToStart:
			hostIds.append(inst['InstanceId'])
		logger.info('Starting instances with ids: {}'.format(str(hostIds)))
		client.start_instances(InstanceIds=hostIds)
		buildMessageForSQS('Started',instancesToStart)
		
	if not instancesToStop:
		logger.info('No instances to stop!')
	else:
		hostIds=[]
		for inst in instancesToStop:
			hostIds.append(inst['InstanceId'])
		logger.info('Stopping instances with ids: {}'.format(str(hostIds)))
		client.stop_instances(InstanceIds=instancesToStop)
		buildMessageForSQS('Stopped',instancesToStop)
		
	return{
		'message' : "Trigger function finished"
	}
