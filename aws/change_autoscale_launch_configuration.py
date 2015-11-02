from boto.ec2 import autoscale
from boto import ec2
from boto import exception
from pprint import pprint, pformat
from copy import copy

import argparse
import sys

parser = argparse.ArgumentParser(description="AutoScale Launch Config updater")
parser.add_argument('--image_id', metavar='image_id')
parser.add_argument('--instance-type', metavar='instance_type')
parser.add_argument('--region', default='eu-west-1', metavar='region')
parser.add_argument('launch_config_name')
parser.add_argument('autoscale_group_name')
args = parser.parse_args()

if not args.image_id and not args.instance_type:
  print("Specify at least one of image_id or instance_type")
  sys.exit(0)

ec2 = ec2.connect_to_region(args.region)
try:
  if args.image_id:
    ec2.get_all_images(image_ids=[args.image_id])
except exception.EC2ResponseError:
  print("It seems that '{0}' is not a valid image_id name or it does not exist  ".format(args.image_id))
  sys.exit(1)

autoscale = autoscale.connect_to_region(args.region)

try:
  as_launch_config = autoscale.get_all_launch_configurations(names = [args.launch_config_name]).pop()
except IndexError:
  print ("Couldn't found AutoScaling Launch Configuration")
  sys.exit(1)

try:
  as_group = autoscale.get_all_groups(names=[args.autoscale_group_name])[0]
except IndexError:
  print("Couldn't found autoscale group '{0}'".format(args.autoscale_group_name))

as_launch_config_tmp = copy(as_launch_config)
as_launch_config_new = copy(as_launch_config)

as_launch_config_tmp.name = "{0}-tmp".format(as_launch_config.name)
print("Creating temporary AutoScaling Launch Config named: {0}".format(as_launch_config_tmp.name))
autoscale.create_launch_configuration(as_launch_config_tmp)

print("Setting AutoScaling Group Launch Configuration to {0}".format(as_launch_config_tmp.name))
as_group = autoscale.get_all_groups(names=[args.autoscale_group_name])[0]
setattr(as_group, 'launch_config_name', as_launch_config_tmp.name)
as_group.update()

# Delete old AutoScale Launch Configuration
print("Deleting old AutoScaling Launch Config named: {0}".format(as_launch_config.name))
as_launch_config.delete()

if args.image_id != None and as_launch_config_new.image_id != args.image_id:
  as_launch_config_new.image_id = args.image_id
if args.instance_type != None and as_launch_config_new.instance_type != args.instance_type:
  as_launch_config_new.instance_type = args.instance_type

autoscale.create_launch_configuration(as_launch_config_new)
print("Setting new AutoScaling Launch Configuration named: {0}".format(as_launch_config_new.name))
setattr(as_group, 'launch_config_name', as_launch_config_new.name)
as_group.update()

print("Cleaning up intermediate Launch Configuration: {0}".format(as_launch_config_tmp.name))
as_launch_config_tmp.delete()

