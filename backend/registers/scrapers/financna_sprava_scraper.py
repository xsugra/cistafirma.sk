import requests
import zipfile
import os
import xml.etree.ElementTree as ET
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

def download_and_parse_fs_data(url: str, data_dir: str = "data/fs_data"):
    """
    Downloads a ZIP file from financna sprava, extracts it, and parses the XML.

    Args:
        url (str): The URL of the ZIP file to download.
        data_dir (str): The directory to store downloaded and extracted files.

    Returns:
        list: A list of dictionaries, where each dictionary represents an item from the XML.
              Returns None on failure.
    """
    try:
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)

        # Download the file
        logger.info(f"Downloading data from {url}")
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        zip_filename = os.path.basename(url)
        zip_path = os.path.join(data_dir, zip_filename)

        with open(zip_path, "wb") as f:
            f.write(response.content)

        logger.info(f"Downloaded {zip_filename} to {zip_path}")

        # Extract the ZIP file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # The folder inside the zip has the same name as the zip file without extension
            extract_folder_name = os.path.splitext(zip_filename)[0]
            extract_path = os.path.join(data_dir, extract_folder_name)
            zip_ref.extractall(extract_path)
            logger.info(f"Extracted to {extract_path}")

        # Find XML file
        xml_filename = f"{extract_folder_name}.xml"
        xml_path = os.path.join(extract_path, xml_filename)

        if not os.path.exists(xml_path):
            # Try to find any xml file in the directory
            xml_files = [f for f in os.listdir(extract_path) if f.endswith('.xml')]
            if not xml_files:
                logger.error(f"XML file not found in {extract_path}")
                return None
            xml_filename = xml_files[0]
            xml_path = os.path.join(extract_path, xml_filename)


        # Parse the XML
        logger.info(f"Parsing XML file: {xml_path}")
        tree = ET.parse(xml_path)
        root = tree.getroot()

        items = []
        # The data items are usually under a tag like 'DS_DSDD' and then in 'ITEM' tags
        # This might need to be more robust if the structure varies a lot.
        for item_element in root.findall(".//ITEM"):
            item_data = {}
            for child in item_element:
                item_data[child.tag] = child.text
            items.append(item_data)
        
        logger.info(f"Parsed {len(items)} items from {xml_filename}")
        
        # Optional: Clean up downloaded and extracted files
        # os.remove(zip_path)
        # import shutil
        # shutil.rmtree(extract_path)

        return items

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while downloading {url}: {e}")
        return None
    except zipfile.BadZipFile:
        logger.error(f"Error extracting ZIP file from {url}. It might be corrupted or not a zip file.")
        return None
    except ET.ParseError as e:
        logger.error(f"Error parsing XML from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred for {url}: {e}")
        return None
