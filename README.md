# amazon-ec2-lambda
dns-route53.py allows to update route53 dns routes using a given hostname/domain passed into the userdata of ec2 instance and the private ip address from a private VPC.

User data should be as follow:

```json
{
    "hostname": "your-marvelous-hostname",
    "domainname": "your-marvelous-domain.com",
    "aliases": ["your-incredible-alias-1","your-incredible-alias-2"]
}
```

star-stop-instances.py allows to start stop instances based on a 'Schedule' tag, that should be set to 'office_hours' or 'always'. Once trigerred the script will make sure instances with tag office_hours are started in during office hours and stopped otherwise. Instances with tag always, will be started if not already running.
