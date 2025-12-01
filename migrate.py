import argparse
import chardet
import csv
import os
import sys
import yaml
import re

MIN_PYTHON = (3, 10, 0)
if sys.version_info < MIN_PYTHON:
    sys.exit(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}.{MIN_PYTHON[2]} or later is required.\n")

# List of reserved tag names that need to be prefixed with 'sw_'
RESERVED_TAGS = {'host', 'device', 'source', 'service', 'env', 'version', 'team'}

# Default columns to use for tags
DEFAULT_TAG_COLUMNS = 'Caption,Location'

def parse_arguments():
    parser = argparse.ArgumentParser(description='Generate DataDog SNMP YAML configuration from SolarWinds CSV files (Individual instances format).')
    parser.add_argument('csv_file', type=str, help='Path to the SolarWinds CSV file containing node data.')
    parser.add_argument('-o', '--output', type=str, help='Optional path to write the YAML configuration file. If omitted, prints to stdout.')

    parser.add_argument('-t', '--tag-columns', type=str, default=DEFAULT_TAG_COLUMNS,
                        help='Comma-separated list of CSV columns to use for tags. Format: column1:tag1,column2:tag2. If tag name not specified, column name in lowercase is used.')

    parser.add_argument('-u', '--user', type=str, help='SNMPv3 username to use instead of PLACEHOLDER_USER.')
    parser.add_argument('-a', '--authprotocol', type=str, choices=['MD5', 'SHA', 'SHA224', 'SHA256', 'SHA384', 'SHA512'],
                        help='SNMPv3 authentication protocol to use instead of PLACEHOLDER_AUTHPROTOCOL.')
    parser.add_argument('-p', '--privprotocol', type=str, choices=['DES', 'AES', 'AES192', 'AES192C', 'AES256', 'AES256C'],
                        help='SNMPv3 privacy protocol to use instead of PLACEHOLDER_PRIVPROTOCOL.')

    return parser.parse_args()

def detect_encoding(file_path, sample_size=32768):
    """Detect the encoding of a file using chardet."""
    print(f"Attempting to detect encoding for {file_path} using chardet...")
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(sample_size)

        result = chardet.detect(raw_data)
        detected_encoding = result['encoding']
        confidence = result['confidence']

        if detected_encoding:
            print(f"Chardet detected encoding: {detected_encoding} with confidence {confidence:.2f}")
            if detected_encoding.lower() == 'ascii':
                 print("Chardet detected ASCII, will attempt reading as utf-8 as it's a superset.")
                 return 'utf-8'
            return detected_encoding
        else:
            print("Chardet could not detect encoding confidently. Falling back to utf-8-sig.")
            return 'utf-8-sig'

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        raise
    except Exception as e:
        print(f"Error during encoding detection: {e}. Falling back to utf-8-sig.")
        return 'utf-8-sig'

def sanitize_value(value):
    """Sanitize a single value by removing or replacing invalid characters."""
    if value is None:
        return value

    # Handle different types of values
    if isinstance(value, (list, tuple)):
        # Convert list/tuple to string representation
        value = str(value)
    elif not isinstance(value, str):
        # Convert other types to string
        value = str(value)

    try:
        # First try to encode as latin1 and decode as UTF-8
        return value.encode('latin1').decode('utf-8', errors='replace')
    except (UnicodeEncodeError, UnicodeDecodeError):
        # If that fails, try to clean the string
        try:
            # Remove any non-printable characters
            return ''.join(char for char in value if char.isprintable())
        except Exception:
            # If all else fails, return empty string
            return ''

def read_csv_file(file_path):
    """Read, sanitize, and parse the SolarWinds CSV file."""
    configs = []
    device_types = {}
    total_rows = 0

    # Detect encoding first
    file_encoding = detect_encoding(file_path)

    try:
        with open(file_path, newline='', encoding=file_encoding) as csvfile:
            csvreader = csv.DictReader(csvfile)

            # Sanitize fieldnames if they exist
            if csvreader.fieldnames:
                # Ensure fieldnames are strings before sanitizing
                safe_fieldnames = [str(fieldname) if fieldname is not None else '' for fieldname in csvreader.fieldnames]
                sanitized_fieldnames = [sanitize_value(fieldname) for fieldname in safe_fieldnames]
                csvreader.fieldnames = sanitized_fieldnames

            for row_dict in csvreader:
                total_rows += 1
                sanitized_row = {}
                if row_dict is None:
                    print(f"Warning: Skipping empty row {total_rows+1}")
                    continue

                for key, value in row_dict.items():
                     # Sanitize key (ensure it's a string first)
                    sanitized_key = sanitize_value(str(key)) if key is not None else None
                    # Sanitize value (sanitize_value already handles None/types)
                    sanitized_row[sanitized_key] = sanitize_value(value)

                # Track device types using sanitized data
                device_type = sanitized_row.get('ObjectSubType', 'Unknown')
                device_types[device_type] = device_types.get(device_type, 0) + 1
                if device_type == 'SNMP':
                    configs.append(sanitized_row) # Add the fully sanitized row

    except UnicodeDecodeError as e:
         print(f"\nError: Failed to decode {file_path} using detected encoding '{file_encoding}'.")
         print(f"Try checking the file's actual encoding or manually specifying it if known.")
         print(f"Specific error: {e}")
         raise
    except FileNotFoundError:
         print(f"Error: File not found at {file_path}")
         raise
    except Exception as e:
         print(f"\nAn unexpected error occurred while reading {file_path}: {e}")
         raise

    print(f"Read and sanitized {total_rows} rows from CSV file with ObjectSubType:")
    for device_type, count in sorted(device_types.items()):
        print(f"  - {device_type}: {count}")

    return configs

def sanitize_tag(text):
    """Sanitize tag key or value to only contain allowed characters."""
    if not text:
        return text
    
    # Convert to string if not already
    text = str(text)
    
    # Replace any character that's not alphanumeric, underscore, minus, colon, period, or slash with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_\-:./]', '_', text)
    
    # Remove any consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    return sanitized

def get_tags(row, tag_columns):
    """Generate tags from device information using specified columns."""
    tags = []
    
    # Parse tag columns specification
    for col_spec in tag_columns.split(','):
        # Split on colon if tag name is specified
        parts = col_spec.split(':')
        col_name = parts[0].strip()
        tag_name = parts[1].strip().lower() if len(parts) > 1 else col_name.lower()
        
        # Add tag if column exists and has value
        if col_name in row and row[col_name]:
            # Sanitize both the tag name and value
            sanitized_tag = sanitize_tag(tag_name)
            sanitized_value = sanitize_tag(row[col_name])
            
            # Add sw_ prefix if tag name is reserved
            if sanitized_tag in RESERVED_TAGS:
                sanitized_tag = f"sw_{sanitized_tag}"
            
            if sanitized_tag and sanitized_value:  # Only add if both parts are non-empty after sanitization
                tags.append(f"{sanitized_tag}:{sanitized_value}")
    
    return tags

def get_snmp_auth_config(row, snmp_version, snmpv3_user=None, snmpv3_authprotocol=None, snmpv3_privprotocol=None):
    """Get SNMP authentication configuration based on SNMP version."""
    if snmp_version in [1, 2]:
        return {
            'community_string': 'PLACEHOLDER_COMMUNITY_STRING'
        }
    elif snmp_version == 3:
        return {
            'user': snmpv3_user if snmpv3_user else 'PLACEHOLDER_USER',
            'authProtocol': snmpv3_authprotocol if snmpv3_authprotocol else 'PLACEHOLDER_AUTHPROTOCOL',
            'authKey': 'PLACEHOLDER_AUTHKEY',
            'privProtocol': snmpv3_privprotocol if snmpv3_privprotocol else 'PLACEHOLDER_PRIVPROTOCOL',
            'privKey': 'PLACEHOLDER_PRIVKEY'
        }

def generate_multi_instance_config(configs, snmpv3_user=None, snmpv3_authprotocol=None, snmpv3_privprotocol=None, tag_columns=DEFAULT_TAG_COLUMNS):
    """Generate a single Datadog YAML configuration file with multiple SNMP device instances."""
    instances = []
    skipped_rows = 0
    
    for row in configs:
        # Skip rows without IP_Address
        if 'IP_Address' not in row or not row['IP_Address']:
            skipped_rows += 1
            continue
        
        tags = get_tags(row, tag_columns)
        
        # Determine SNMP version from the CSV data
        # Default to version 2 if not specified or invalid
        snmp_version = 2
        if 'SNMPVersion' in row and row['SNMPVersion']:
            try:
                version = int(row['SNMPVersion'])
                if version in [1, 2, 3]:
                    snmp_version = version
            except (ValueError, TypeError):
                pass  # Keep the default if conversion fails
        
        snmp_auth = get_snmp_auth_config(row, snmp_version, snmpv3_user, snmpv3_authprotocol, snmpv3_privprotocol)
        
        # Check for valid PollInterval
        min_collection_interval = None
        if 'PollInterval' in row and row['PollInterval']:
            try:
                interval = int(row['PollInterval'])
                if interval > 0:
                    min_collection_interval = interval
            except (ValueError, TypeError):
                pass  # Skip invalid values
        
        instance = {
            'ip_address': row['IP_Address'],
            'port': int(row['AgentPort']) if row.get('AgentPort') is not None and row.get('AgentPort') != '' else 161,  # Default to 161 if not specified
            'snmp_version': snmp_version,
            **snmp_auth,
            'tags': tags
        }
        
        # Add min_collection_interval if we found a valid value
        if min_collection_interval is not None:
            instance['min_collection_interval'] = min_collection_interval
        
        instances.append(instance)
    
    if skipped_rows > 0:
        print(f"Skipped {skipped_rows} rows due to missing IP_Address", file=sys.stderr)
    
    config = {
        'init_config': {
            'loader': 'core',
            'use_device_id_as_hostname': True
        },
        'instances': instances
    }
    return config

def write_yaml_file(config, output_path):
    """Write the configuration to a YAML file."""
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        print(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir)
    
    # Check if file exists and ask for confirmation
    if os.path.exists(output_path):
        response = input(f"Warning: File {output_path} already exists. Overwrite? [y/N] ").lower()
        if response != 'y':
            print("Operation cancelled.")
            sys.exit(0)
    
    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Configuration written to {output_path}")

def main():
    args = parse_arguments()
    
    # Read and process CSV file
    configs = read_csv_file(args.csv_file)
    
    # Generate configuration with multiple instances
    config = generate_multi_instance_config(configs, args.user, args.authprotocol, args.privprotocol, args.tag_columns)
    
    if args.output:
        output_path = args.output
        write_yaml_file(config, output_path)
    else:  # If no output file, print YAML to stdout
        print(yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True))

if __name__ == "__main__":
    main()
