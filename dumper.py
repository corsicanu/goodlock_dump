import argparse
import os
import time
import shutil
import requests
import xml.etree.ElementTree as ET
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from colorama import Fore, Style, init

# Initialize colored console output
init(autoreset=True)

# === Step 1: Parse Command Line Arguments ===
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--deviceId", required=True)
parser.add_argument("-s", "--sdk", required=True)
parser.add_argument("-o", "--os", required=True)
parser.add_argument("-c", "--csc", required=True)
parser.add_argument("-v", "--version", required=True)
args = parser.parse_args()

# === Step 2: Prepare Directories ===
xml_dir = "xml"
app_dir = os.path.join("releases", args.sdk)

os.makedirs(xml_dir, exist_ok=True)
os.makedirs(app_dir, exist_ok=True)

# Clean up old files
xml_file = os.path.join(xml_dir, f"{args.sdk}.xml")
if os.path.exists(xml_file):
    os.remove(xml_file)

if os.path.exists("versions.txt"):
    os.remove("versions.txt")
with open("versions.txt", "a") as versions_file:
    versions_file.write("Included apps and versions:\n")

# === Step 3: Create Session with Retry Logic ===
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"],
)
session.mount("http://", HTTPAdapter(max_retries=retries))
session.mount("https://", HTTPAdapter(max_retries=retries))

def safe_get(url, timeout=20):
    """Wrapper for GET requests with retry and timeout."""
    try:
        return session.get(url, timeout=timeout)
    except requests.exceptions.RequestException as e:
        print(Fore.RED + f"[ERROR] Request failed for {url}: {e}")
        return None

# === Step 4: Get Main App List XML ===
base_url = "http://vas.samsungapps.com/product/getContentCategoryProductList.as"
query_params = {
    "contentCategoryID": "0000005309",
    "versionCode": "301001000",
    "mcc": "262",
    "mnc": "01",
    "csc": args.csc,
    "deviceId": args.deviceId,
    "sdkVer": args.sdk,
    "callerId": "com.samsung.android.goodlock",
    "extuk": "0191d6627f38685f",
    "abiType": "64",
    "oneUiVersion": args.version,
    "cc": "NONE",
    "imgWidth": "512",
    "imgHeight": "512",
    "startNum": "1",
    "endNum": "100",
    "alignOrder": "alphabetical",
    "installInfo": "Y",
    "pd": "0"
}
url = f"{base_url}?{'&'.join([f'{key}={value}' for key, value in query_params.items()])}"

print(Fore.CYAN + f"\n[INFO] Fetching app list for SDK {args.sdk}...")
print(Fore.LIGHTBLACK_EX + f"[DEBUG] {url}")

response = safe_get(url)
if not response or response.status_code != 200:
    print(Fore.RED + "[ERROR] Failed to fetch app list.")
    exit(1)

with open(xml_file, "wb") as tmp_file:
    tmp_file.write(response.content)

# === Step 5: Parse XML for App IDs ===
tree = ET.parse(xml_file)
root = tree.getroot()
app_ids = [element.text for element in root.findall(".//appId")]

total_apps = len(app_ids)
print(Fore.GREEN + f"[INFO] Found {total_apps} apps to process.\n")

# === Step 6: Process Each App ===
for idx, app_id in enumerate(app_ids, start=1):
    subsequent_url = (
        f"https://vas.samsungapps.com/stub/stubDownload.as"
        f"?appId={app_id}&callerId=com.samsung.android.goodlock"
        f"&callerVersion=301001000&extuk=0191d6627f38685f"
        f"&deviceId={args.deviceId}&mcc=262&mnc=01&csc={args.csc}"
        f"&sdkVer={args.sdk}&abiType=64&oneUiVersion={args.version}"
        f"&isAutoUpdate=0&cc=NONE&pd=0&updateType=ond&versionCode=-1"
    )

    print(Fore.YELLOW + f"[{idx}/{total_apps}] Checking appId: {app_id}")
    print(Fore.LIGHTBLACK_EX + f"└─ {subsequent_url}")

    subsequent_response = safe_get(subsequent_url)
    if not subsequent_response or subsequent_response.status_code != 200:
        print(Fore.RED + f"  └─ Skipped (failed request)")
        continue

    # Parse XML for details
    try:
        subsequent_tree = ET.fromstring(subsequent_response.text)
        sub_app_id = subsequent_tree.find(".//appId").text
        download_uri = subsequent_tree.find(".//downloadURI").text
        product_name = subsequent_tree.find(".//productName").text
        version_name = subsequent_tree.find(".//versionName").text
    except Exception as e:
        print(Fore.RED + f"  └─ XML parse error: {e}")
        continue

    if not download_uri:
        print(Fore.RED + f"  └─ Missing download URI for {sub_app_id}")
        continue

    print(Fore.BLUE + f"  ├─ {product_name} v{version_name}")
    print(Fore.LIGHTBLACK_EX + f"  ├─ Download: {download_uri}")

    # Download the APK
    response = safe_get(download_uri)
    if not response or response.status_code != 200:
        print(Fore.RED + "  └─ Failed to download APK")
        continue

    file_name = os.path.join(app_dir, f"{sub_app_id}.apk")
    with open(file_name, "wb") as apk_file:
        apk_file.write(response.content)

    with open("versions.txt", "a") as versions_file:
        versions_file.write(f"- {product_name} {version_name}\n")

    print(Fore.GREEN + f"  └─ Downloaded: {file_name}\n")

    # Optional short pause to avoid rate limiting
    time.sleep(1)

print(Fore.CYAN + "\n[INFO] Dump completed successfully!")
print(Fore.CYAN + f"[INFO] Files saved in: {app_dir}")
print(Fore.CYAN + f"[INFO] Version log: versions.txt\n")
