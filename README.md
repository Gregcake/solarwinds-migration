# SolarWinds to DataDog Migration Tool User's Guide

This tool converts SolarWinds SNMP device configuration from a CSV
export file into DataDog SNMP device YAML configuration files. It
supports both SNMPv1/v2c and SNMPv3 configurations, with customizable
tag generation from CSV columns.

## Requirements from user

-   SolarWinds CSV export file containing node data

## Obtaining the SolarWinds CSV Export

1.  Open SolarWinds Database Manager
2.  Connect to your SolarWinds database
3.  Run the following SQL query:

```sql
SELECT * FROM [dbo].[Nodes]
```

4.  Export the results as a CSV file named **Nodes.csv**
    -   Make sure to include column headers
    -   The file must contain at least this column: `IP_Address`
5.  If the CSV file contains a **Community** column, remove it before
    sending to Datadog:

``` bash
pip install csvkit
# use the proper encoding for your system type/CSV file encoding
csvcut --encoding windows-1252 -C "Community" Nodes.csv > tmp.csv && mv tmp.csv Nodes.csv
```

## CSV Column Mappings

| CSV Column | YAML Field | Description |
| ---------- | ---------- | ----------- |
| IP_Address | ip_address | Required. The IP address of the SNMP device |
| SNMPVersion | snmp_version |SNMP version (1, 2, or 3; defaults to 2) |
| AgentPort | port | SNMP port (defaults to 161) |
| PollInterval | min_collection_interval | Polling interval in seconds (defaults to 15)|
| Caption | tag:caption | Device description |
| Location | tag:location | Device location |

### Custom Tag Columns

Specific columns can be mapped to tags using the -t/--tag-columns option, which will override the defaults. For example:

``` bash
# Map 'Department' column to a 'dept' tag
python migrate.py Nodes.csv -t "Department:dept"
```

## Get the Migration Tool
Repository:
https://github.com/DataDog/ndm-tools/tree/main/solarwinds-migration

Clone:

``` bash
cd ~/dd
git clone https://github.com/Gregcake/solarwinds-migration.git
```

## Install Python Requirements
### Requirements
-   Python 3.10 or later
-   Required Python packages (see requirements.txt):
    - chardet
    - pyyaml

Install the required Python packages using pip:
``` bash
cd ~/dd/ndm-tools/solarwinds-migration
pip install -r requirements.txt
```

# Migration Tool Usage

    python migrate.py input.csv [-o output.yaml] [-t tag_columns] [-u user] [-a authprotocol] [-p privprotocol]

## Required Arguments
- `input.csv`: Path to the SolarWinds CSV export file containing node data

## Optional Arguments
- `-o`, `--output`: Path to write the YAML configuration file. If omitted, prints to stdout
- `-t`, `--tag-columns`: Comma-separated list of CSV columns to use for tags
    - Format: column1:tag1,column2:tag2
    - If tag name not specified, column name in lowercase is used
    - Default: Caption,Location
- `-u`, `--user`: SNMPv3 username to use instead of PLACEHOLDER_USER
- `-a`, `--authprotocol`: SNMPv3 authentication protocol
    - Valid options: MD5, SHA, SHA224, SHA256, SHA384, SHA512
    - Default: PLACEHOLDER_AUTHPROTOCOL
- `-p`, `--privprotocol`: SNMPv3 privacy protocol
  - Valid options: DES, AES, AES192, AES192C, AES256, AES256C
  - Default: PLACEHOLDER_PRIVPROTOCOL
 
# Tag Handling
The tool processes tags according to the following rules:
- Tags are generated from either the default columns (Caption,Location) or from columns specified in the --tag-columns argument, which overrides the defaults
- Tag names and values are sanitized to only contain:
  - Alphanumerics (`a-z`, `A-Z`, `0-9`)
  - Underscores (`_`)
  - Minuses (`-`)
  - Colons (`:`)
  - Periods (`.`)
  - Slashes (`/`)
- Special characters and spaces are converted to underscores
- The following tag names are reserved and will be prefixed with sw_:
  - host
  - device
  - source
  - service
  - env
  - version
  - team

# SNMP Configuration & Credentials
The migration tool does not handle actual credentials, both to avoid potentially exposing credentials when sending configuration files, and because credentials are typically encrypted in the SolarWinds database tables.  Instead, the migration tools will insert placeholders for SNMPv2 and SNMPv3 credentials.
### SNMPv1/v2c
- Uses community string authentication
- Community string is set to PLACEHOLDER_COMMUNITY_STRING
### SNMPv3
- Supports authentication and privacy protocols
- Default placeholders:
  - user: PLACEHOLDER_USER
  - authProtocol: PLACEHOLDER_AUTHPROTOCOL
  - authKey: PLACEHOLDER_AUTHKEY
  - privProtocol: PLACEHOLDER_PRIVPROTOCOL
  - privKey: PLACEHOLDER_PRIVKEY

# Deploying to DataDog Agent
After generating the configuration file:
Copy the generated YAML file to the DataDog agent configuration directory:
```
sudo cp conf.yaml /etc/datadog/conf.d/snmp.d/conf.yaml
```
Replace the placeholder credentials with actual credentials.  For example,
```
sed -i '.bak' 's/PLACEHOLDER_USER/actual_username/g' /etc/datadog/conf.d/snmp.d/conf.yaml
```
Restart the DataDog agent to apply the new configuration:
```
sudo systemctl restart datadog-agent
```
Verify the configuration is loaded:
```
sudo datadog-agent status
```

# Examples

## Basic Usage

``` bash
# Convert the SolarWinds export to DataDog YAML
python migrate.py Nodes.csv
# Save the output to a file
python migrate.py Nodes.csv -o conf.yaml
```

## Custom Tag Configuration

``` bash
# Use specific columns for tags with custom tag names
python migrate.py Nodes.csv -t "Caption:cap,Location:city"
# Use only certain columns (using default tag names)
python migrate.py Nodes.csv -t "Caption,Location"
```

## SNMPv3 Example

``` bash
# Configure SNMPv3 with authentication
python migrate.py Nodes.csv -u admin -a SHA -p AES
```

## Full Example

``` bash
# Full configuration with all options
python migrate.py Nodes.csv \
  -o conf.yaml \
  -t "Caption:cap,Location:city" \
  -u admin \
  -a SHA \
  -p AES
```
