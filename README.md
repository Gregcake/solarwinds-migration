# SolarWinds to DataDog Migration Tool User's Guide

This tool converts SolarWinds SNMP device configuration from a CSV
export file into DataDog SNMP device YAML configuration files. It
supports both SNMPv1/v2c and SNMPv3 configurations, with customizable
tag generation from CSV columns.

## Requirements from customer

-   SolarWinds CSV export file containing node data

## Obtaining the SolarWinds CSV Export

1.  Open SolarWinds Database Manager
2.  Connect to your SolarWinds database
3.  Run the following SQL query:

```{=html}
<!-- -->
```
    SELECT * FROM [dbo].[Nodes]

4.  Export the results as a CSV file named **Nodes.csv**
    -   Make sure to include column headers
    -   The file must contain at least this column: `IP_Address`
5.  If the CSV file contains a **Community** column, remove it before
    sending to Datadog:

``` bash
pip install csvkit
csvcut --encoding windows-1252 -C "Community" Nodes.csv > tmp.csv && mv tmp.csv Nodes.csv
```

## CSV Column Mappings

  -----------------------------------------------------------------------------
  CSV Column     YAML Field                Description
  -------------- ------------------------- ------------------------------------
  IP_Address     ip_address                Required. The IP address of the SNMP
                                           device

  SNMPVersion    snmp_version              SNMP version (1, 2, or 3; defaults
                                           to 2)

  AgentPort      port                      SNMP port (defaults to 161)

  PollInterval   min_collection_interval   Polling interval in seconds

  Caption        tag:caption               Device description

  Location       tag:location              Device location
  -----------------------------------------------------------------------------

### Custom Tag Columns

``` bash
python migrate.py Nodes.csv -t "Department:dept"
```

## Get the Migration Tool

Repository:
https://github.com/DataDog/ndm-tools/tree/main/solarwinds-migration

Clone:

``` bash
cd ~/dd
git clone git@github.com:DataDog/ndm-tools.git
```

Install dependencies:

``` bash
cd ~/dd/ndm-tools/solarwinds-migration
pip install -r requirements.txt
```

# Migration Tool Usage

    python migrate.py input.csv [-o output.yaml] [-t tag_columns] [-u user] [-a authprotocol] [-p privprotocol]

## Tag Handling Rules

-   Uses defaults (Caption, Location) unless overridden\
-   Only alphanumerics, `_ - : . /` allowed\
-   Special characters → underscores\
-   Reserved tag names (host, device, service, etc.) prefixed with `sw_`

# SNMP Configuration & Credentials

### SNMPv1/v2c placeholders

    PLACEHOLDER_COMMUNITY_STRING

### SNMPv3 placeholders

    PLACEHOLDER_USER
    PLACEHOLDER_AUTHPROTOCOL
    PLACEHOLDER_AUTHKEY
    PLACEHOLDER_PRIVPROTOCOL
    PLACEHOLDER_PRIVKEY

# Deploying to DataDog Agent

``` bash
sudo cp conf.yaml /etc/datadog/conf.d/snmp.d/conf.yaml
sed -i '.bak' 's/PLACEHOLDER_USER/actual_username/g' /etc/datadog/conf.d/snmp.d/conf.yaml
sudo systemctl restart datadog-agent
sudo datadog-agent status
```

# Examples

## Basic Usage

``` bash
python migrate.py Nodes.csv
python migrate.py Nodes.csv -o conf.yaml
```

## Custom Tag Configuration

``` bash
python migrate.py Nodes.csv -t "Caption:cap,Location:city"
python migrate.py Nodes.csv -t "Caption,Location"
```

## SNMPv3 Example

``` bash
python migrate.py Nodes.csv -u admin -a SHA -p AES
```

## Full Example

``` bash
python migrate.py Nodes.csv   -o conf.yaml   -t "Caption:cap,Location:city"   -u admin   -a SHA   -p AES
```
