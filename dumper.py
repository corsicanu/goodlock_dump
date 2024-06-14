import argparse
import os
import time
import shutil
import requests
import xml.etree.ElementTree as ET

# Step 1: Parse Command Line Arguments
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--deviceId", required=True)
parser.add_argument("-s", "--sdk", required=True)
parser.add_argument("-o", "--os", required=True)
parser.add_argument("-c", "--csc", required=True)
parser.add_argument("-v", "--version", required=True)
args = parser.parse_args()

# Create the XML directory if it doesn't exist
xml_dir = f"xml"
os.makedirs(xml_dir, exist_ok=True)

# Create the app directory
app_dir = os.path.join("releases", args.sdk)
os.makedirs(app_dir, exist_ok=True)

# Remove the XML file for sdk if exists
if os.path.exists(os.path.join("xml", f"{args.sdk}.xml")):
    os.remove(os.path.join("xml", f"{args.sdk}.xml"))

# Remove the versions.txt file if exists and recreate it
if os.path.exists("versions.txt"):
    os.remove("versions.txt")
with open("versions.txt", "a") as versions_file:
    versions_file.write(f"Included apps and versions: \n")

# Step 2: Construct URL
base_url = "http://vas.samsungapps.com/product/getContentCategoryProductList.as"
query_params = {
    "contentCategoryID": "0000005309",
    "deviceId": args.deviceId,
    "sdkVer": args.sdk,
    "mcc": "262",
    "mnc": "01",
    "csc": args.csc,
    "imgWidth": "512",
    "imgHeight": "512",
    "startNum": "1",
    "endNum": "100",
    "alignOrder": "alphabetical",
    "callerId": "com.samsung.android.goodlock",
    "cc": "NONE",
    "systemId": "0",
    "abiType": "64",
    "oneUiVersion": args.version,
}
url = f"{base_url}?{'&'.join([f'{key}={value}' for key, value in query_params.items()])}"

# Calculate systemId (current epoch time minus 180 seconds)
current_time = int(time.time())
system_id = current_time - 180

# Update query_params with the new systemId
query_params["systemId"] = str(system_id)

# Reconstruct the URL with the updated systemId
url = f"{base_url}?{'&'.join([f'{key}={value}' for key, value in query_params.items()])}"

# Step 3: Perform Initial cURL Request and Save to tmp file
response = requests.get(url)
if response.status_code == 200:    
    with open(f"{xml_dir}/{args.sdk}.xml", "wb") as tmp_file:
        tmp_file.write(response.content)

# Step 4: Parse the Initial XML and Extract "appId" fields
tree = ET.parse(f"{xml_dir}/{args.sdk}.xml")
root = tree.getroot()

# Extract "appId" elements without considering namespaces
app_ids = [element.text for element in root.findall(".//appId")]

# Step 5: Loop through extracted "appId" values
for app_id in app_ids:
    # Step 6: Construct Subsequent URL
    subsequent_url = f"https://vas.samsungapps.com/stub/stubDownload.as?appId={app_id}&deviceId={args.deviceId}&mcc=262&mnc=01&csc={args.csc}&sdkVer={args.sdk}&pd=0&systemId={system_id}&callerId=com.sec.android.app.samsungapps&abiType=64&extuk=0191d6627f38685f"

    # Step 7: Perform Subsequent cURL Request
    subsequent_response = requests.get(subsequent_url)
    
    if subsequent_response.status_code == 200:
        # Step 8: Parse Subsequent XML and Extract Data
        subsequent_tree = ET.fromstring(subsequent_response.text)
        sub_app_id = subsequent_tree.find(".//appId").text
        download_uri = subsequent_tree.find(".//downloadURI").text
        product_name = subsequent_tree.find(".//productName").text
        version_name = subsequent_tree.find(".//versionName").text
        
        # Check if download_uri is not None
        if download_uri:
            # Step 9: Download Files and Save
            response = requests.get(download_uri)
            if response.status_code == 200:                
                print(f"Found app {product_name} with version {version_name}")
                file_name = f"{app_dir}/{sub_app_id}.apk"
                
                with open(file_name, "wb") as apk_file:
                    apk_file.write(response.content)
                
                # Write down versions
                with open("versions.txt", "a") as versions_file:
                    versions_file.write(f"- {product_name} {version_name} \n")
        else:
            print(f"Warning: 'download_uri' is None for appId: {sub_app_id}")
