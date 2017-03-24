# amazon-ec2-lambda

## dns-route53.py

This script allows to update route53 dns routes using a given hostname/domain passed into the tags or userdata of ec2 instance and the private ip address from a private VPC.

First script will look into the tags of the instance: Hostname, Domainname, Aliases

![Alt text](sc/sc1.png?raw=true "Tags on EC2 instance")

If one of Hostname or Domain tag is not found, then script will check user data for following JSON

User data should be as follow:

```json
{
    "hostname": "your-marvelous-hostname",
    "domainname": "your-marvelous-domain.com",
    "aliases": ["your-incredible-alias-1","your-incredible-alias-2"]
}
```

##star-stop-instances.py

This script allows to start stop instances based on a 'Schedule' tag, that should be set to 'office_hours' or 'always'. Once trigerred the script will make sure instances with tag office_hours are started in during office hours and stopped otherwise. Instances with tag always, will be started if not already running.
