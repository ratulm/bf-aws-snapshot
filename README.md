Scripts to fetch AWS data and package it as a Batfish snapshot.

## Setup

- Python3 

- `pip install -r requirements.txt`
 
- [Set up AWS credentials](https://docs.aws.amazon.com/sdk-for-java/v1/developer-guide/setup-credentials.html) 
  - run `python aws_data_getter.py -t` to see if the credentials are properly setup

## Fetching AWS data

 - `python aws_data_getter.py` 

    This command will take a snapshot of your AWS configurations and put it in `aws-snapshot` folder. To specify a different folder, use the `-o` option. 

    The command reads its config data from `config.json`. You may supply a different file using the `-c` option. You may change the contents of this file to control which regions and VPCs the data is fetched from. Unless you know what you are doing, do not mess with the `skipData` configuration.  

    The command used the default AWS profile by default. To use a different (configured) profile, use the `-p` option.
