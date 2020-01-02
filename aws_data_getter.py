from awshelper import aws_get_config, aws_get_regions, aws_init, aws_test_access
from argparse import ArgumentParser, ArgumentTypeError
import json
import os
import shutil
import sys
import traceback

AWS_SUB_FOLDER = "aws_configs"


def _str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise ArgumentTypeError('Boolean value expected.')


def snapshot_configs(output_folder):
    regions = aws_get_regions()  # empty list if we are not doing aws
    for region in regions:
        region_dir = os.path.join(output_folder, AWS_SUB_FOLDER, region)
        os.makedirs(region_dir)
        aws_region_config = aws_get_config(region)
        for key in aws_region_config:
            try:
                filename = os.path.join(region_dir, key + ".json")
                with open(filename, 'w') as f:
                    f.write(json.dumps(aws_region_config[key], indent=1, default=str, sort_keys=True))
            except:
                traceback.print_exc()


def main():
    parser = ArgumentParser(description="archiver")
    parser.add_argument('-c', '--config', dest='config_filename', help="config file", metavar="<file>",
                        default="config.json")
    parser.add_argument('-p', '--profile', dest='profile', help="profile name")
    parser.add_argument('-o', '--output-folder', dest='output_folder', help="output folder", metavar="<file>",
                        default="aws-snapshot")
    parser.add_argument('-t', '--test-access', dest='test_access', help="Test access to AWS and exit", type=_str2bool,
                        nargs='?', default=False, const=True)
    parser.add_argument('-f', '--force', dest='force', help="Overwrite output folder if it already exists",
                        type=_str2bool, nargs='?', default=False, const=True)
    args = parser.parse_args()

    with open(args.config_filename) as config_file:
        options = json.load(config_file)

    regions = options.get("regions", None)
    vpc_ids = options.get("vpcs", None)
    skip_data = options.get("skipData", None)

    if args.test_access:
        aws_test_access(profile=args.profile)
        exit(0)

    if os.path.exists(args.output_folder):
        if args.force:
            shutil.rmtree(args.output_folder)
        else:
            print(
                "Output folder '{}' already exists. Provide a different folder (using '-o' option) or use the '-f' option to overwrite existing folder".format(
                    args.output_folder), file=sys.stderr)
            exit(1)

    aws_init(regions, vpc_ids, skip_data, args.profile)
    snapshot_configs(args.output_folder)


if __name__ == '__main__':
    main()
