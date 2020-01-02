# Demo scripts

This repository contains script to take an AWS snapshot

## Setup

- `pip install -r requirements.txt`
 
- Optional: [Set up AWS credentials](https://docs.aws.amazon.com/sdk-for-java/v1/developer-guide/setup-credentials.html) 
  - run `python awsarchiver.py -t` to see if the credentials are properly setup

## Fetching AWS data

 - `python aws_data_getter.py` 

This command will take a snapshot of your AWS configurations and put it in `aws-snapshot` folder. To specify a different folder, use the `-o` option. 

The command reads its config data from `config.json`. You may supply a different file using the `-c` option. You may change the contents of this file to control which regions and VPCs the data is fetched from. Unless you know what you are doing, do not mess with the `skipData` configuration.  

### Credentials 

There are a few different ways to supply credentials to the script

- Configured AWS profiles: 

`python aws_data_getter.py -p profile-name`

The default profile is used if the `-p` option is not used. 

- Environment variables:

Use the following if you have not setup AWS credentials or want to use different credentials:

`AWS_ACCESS_KEY=XXXXXX AWS_SECRET_KEY=YYYYY python awsarchiver.py`

## Initializing Batfish snapshot

 - `python aws_snapshot_initializer.py`
 
 This command will initialize a snapshot using data in `aws-snapshot` folder. To specify a different folder, use the `--input-folder` option to specify a different folder.
 
 By default, the script assumes that Batfish is running locally. To point at a remote host, use
 
 - `python aws_snapshot_initializer.py -host 36b717811ee15f4.service.intentionet.com --key XXXXX -ssl true`

To test if your access to the Batfish service is working with the provided options, use the `--test-access` option.

By default, the script use "aws" as both network and snapshot names. Use the `--network` and `--snapshot` options to specify different names.
