from datetime import datetime
from operator import itemgetter

from django.contrib.auth import get_user_model
from django.template.defaultfilters import date as _date
from django.utils.text import slugify
import pandas as pd

from client import bulk_update, get_db


def sort_dictionary_list_by_field(list_to_be_sorted, field, reverse=False):
    return sorted(list_to_be_sorted, key=itemgetter(field), reverse=reverse)


def get_month_range(start, end=datetime.now(), fmt="Y F"):
    start = start.month + 12 * start.year
    end = end.month + 12 * end.year
    months = list()
    for month in range(start - 1, end):
        y, m = divmod(month, 12)
        months.insert(0, (f'{y}-{m+1}', _date(datetime(y, m + 1, 1), fmt)))
    return months


def unix_time_millis(dt):
    epoch = datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds() * 1000)


def get_administrative_region_choices(eadl_db, empty_choice=True):
    country_id = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": None,
        }
    )[:][0]['administrative_id']
    query_result = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": country_id,
        }
    )
    choices = list()
    for i in query_result:
        choices.append((i['administrative_id'], f"{i['name']}"))
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_choices(query_result, empty_choice=True):
    choices = [(i['id'], i['name']) for i in query_result]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_issue_age_group_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_age_group'})
    return get_choices(query_result, empty_choice)


def get_issue_citizen_group_1_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_citizen_group_1'})
    return get_choices(query_result, empty_choice)


def get_issue_citizen_group_2_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_citizen_group_2'})
    return get_choices(query_result, empty_choice)


def get_issue_type_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_type'})
    return get_choices(query_result, empty_choice)


def get_issue_category_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_category'})
    return get_choices(query_result, empty_choice)


def get_issue_status_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_status'})
    return get_choices(query_result, empty_choice)


def get_administrative_region_name(eadl_db, administrative_id):
    not_found_message = f'[Missing region with administrative_id "{administrative_id}"]'
    if not administrative_id:
        return not_found_message

    region_names = []
    has_parent = True

    while has_parent:
        docs = eadl_db.get_query_result({
            "administrative_id": administrative_id,
            "type": 'administrative_level'
        })

        try:
            doc = eadl_db[docs[0][0]['_id']]
            region_names.append(doc['name'])
            administrative_id = doc['parent_id']
            has_parent = administrative_id is not None
        except Exception:
            region_names.append(not_found_message)
            has_parent = False

    return ', '.join(region_names)


def get_base_administrative_id(eadl_db, administrative_id, base_parent_id=None):
    base_administrative_id = administrative_id
    while True:
        parent = get_parent_administrative_level(eadl_db, administrative_id)
        if parent:
            base_administrative_id = administrative_id
            administrative_id = parent['administrative_id']
            if base_parent_id and parent['administrative_id'] == base_parent_id:
                break
        else:
            break
    return base_administrative_id


def get_child_administrative_regions(eadl_db, parent_id):
    data = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    data = [doc for doc in data]
    return data


def get_administrative_regions_by_level(eadl_db, level=None):
    filters = {"type": 'administrative_level'}
    if level:
        filters['administrative_level'] = level
    else:
        filters['parent_id'] = None
    parent_id = eadl_db.get_query_result(filters)[:][0]['administrative_id']
    data = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    data = [doc for doc in data]
    return data


def get_administrative_level_descendants(eadl_db, parent_id, ids):
    data = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    data = [doc for doc in data]
    descendants_ids = [region["administrative_id"] for region in data]
    for descendant_id in descendants_ids:
        get_administrative_level_descendants(eadl_db, descendant_id, ids)
        ids.append(descendant_id)

    return ids


def get_parent_administrative_level(eadl_db, administrative_id):
    parent = None
    docs = eadl_db.get_query_result({
        "administrative_id": administrative_id,
        "type": 'administrative_level'
    })

    try:
        doc = eadl_db[docs[0][0]['_id']]
        if 'parent_id' in doc and doc['parent_id']:
            administrative_id = doc['parent_id']
            docs = eadl_db.get_query_result({
                "administrative_id": administrative_id,
                "type": 'administrative_level'
            })
            parent = eadl_db[docs[0][0]['_id']]
    except Exception:
        pass
    return parent


def get_related_region_with_specific_level(eadl_db, region_doc, level):
    """
    Returns the document of type=administrative_level related to the region_doc with
    administrative_level=level. To find it, start from the region_doc and continue
    through its ancestors until it is found, if it is not found, return the region_doc
    """
    has_parent = True
    administrative_id = region_doc['administrative_id']
    while has_parent and region_doc['administrative_level'] != level:
        region_doc = get_parent_administrative_level(eadl_db, administrative_id)
        if region_doc:
            administrative_id = region_doc['administrative_id']
        else:
            has_parent = False

    return region_doc


def belongs_to_region(eadl_db, child_administrative_id, parent_administrative_id):
    if parent_administrative_id == child_administrative_id:
        belongs = True
    else:
        belongs = child_administrative_id in get_administrative_level_descendants(eadl_db, parent_administrative_id, [])
    return belongs


def get_auto_increment_id(grm_db):
    try:
        max_auto_increment_id = grm_db.get_view_result('issues', 'auto_increment_id_stats')[0][0]['value']['max']
    except Exception:
        max_auto_increment_id = 0
    return max_auto_increment_id + 1


def create_facilitators_per_administrative_level(email_domain):
    if not email_domain:
        print("Please specify Email Domain")
        return False

    eadl_db = get_db()
    cells = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "administrative_level": "CELL",
        }
    )
    i = 0
    for cell in cells:
        i = i + 1
        sector = eadl_db.get_query_result(
            {
                "type": 'administrative_level',
                "administrative_level": "SECTOR",
                "administrative_id": cell["parent_id"]
            }
        )[:][0]
        district = eadl_db.get_query_result(
            {
                "type": 'administrative_level',
                "administrative_level": "DISTRICT",
                "administrative_id": sector["parent_id"]
            }
        )[:][0]

        username_press = 'pres.' + slugify(cell["name"]) + '.' + slugify(sector["name"]) + '.' + slugify(district["name"])
        username_vice = 'vice.' + slugify(cell["name"]) + '.' + slugify(sector["name"]) + '.' + slugify(district["name"])

        email_press = f"{username_press}@{email_domain}"
        email_vice = f"{username_vice}@{email_domain}"



        doc_pres = {
              "type": "adl",
              "administrative_region": cell["administrative_id"],
              "name": cell["name"],
              "photo": "",
              "location": {
                "lat": "null",
                "long": "null"
              },
              "representative": {
                "email": email_press,
                "password": "",
                "is_active": True,
                "name": username_press,
                "photo": "",
                "last_active": "null"
              },
              "phases": [],
              "department": 1,
              "administrative_level": "CELL",
              "unique_region": 1,
              "village_secretary": 1
        }

        doc_vice = {
            "type": "adl",
            "administrative_region": cell["administrative_id"],
            "name": cell["name"],
            "photo": "",
            "location": {
                "lat": "null",
                "long": "null"
            },
            "representative": {
                "email": email_vice,
                "password": "",
                "is_active": True,
                "name": username_vice,
                "photo": "",
                "last_active": "null"
            },
            "phases": [],
            "department": 1,
            "administrative_level": "CELL",
            "unique_region": 1,
            "village_secretary": 0
        }
        print("Cell: " + str(i), email_vice, cell["name"])
        print(eadl_db.get_query_result(
            {
                "representative.email": email_press
            }
        )[:])
        if not eadl_db.get_query_result(
            {
                "representative.email": email_vice
            }
        )[:]:
            print("Creating vice")
            eadl_db.create_document(doc_vice)
        else:
            print("Vice already exists")

        if not eadl_db.get_query_result(
            {
                "representative.email": email_press
            }
        )[:]:
            print("Creating press")
            eadl_db.create_document(doc_pres)
        else:
            print("Press already exists")

        # eadl_db.create_document(doc_vice)
        # eadl_db.create_document(doc_pres)
    print("Done")


def fix_administrative_id():
    eadl_db = get_db()
    adls = eadl_db.get_query_result(
        {
            "type": 'adl'
        }
    )
    docs_to_update = []
    i = 0
    for adl in adls:
        i = i + 1
        administrative_level = eadl_db.get_query_result(
            {
                "type": 'administrative_level',
                "_id": adl["administrative_region"]
            }
        )
        print(i)
        if administrative_level[:]:
            adl['administrative_region'] = administrative_level[:][0]['administrative_id']
            docs_to_update.append(adl)
    docs_updated = len(bulk_update(eadl_db, docs_to_update))
    print(docs_updated)
    return 'DONE'


def fix_district_administration():
    eadl_db = get_db()
    adls = eadl_db.get_query_result(
        {
            "type": 'administrative_level',
            "administrative_level": "DISRICT",
        }
    )

    docs_to_update = []
    i = 0
    for adl in adls:
        i = i + 1
        print(adl)
        adl['administrative_level'] = "DISTRICT"
        docs_to_update.append(adl)
        print(adl)
    docs_updated = len(bulk_update(eadl_db, docs_to_update))
    print(docs_updated)

    return '> DONE '


def combine_sheet():
    # Replace 'your_excel_file.xlsx' with the name of your Excel file
    file_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/13SPRPdistricts.xlsx'

    # Specify the columns you want to keep
    columns_to_keep = ["Latitude", "Longitude", "CHW Title", "Name", "District", "Sector", "Cell", "ID No", "Telephone"]

    # Initialize an empty list to store DataFrames
    dfs = []

    # Load each sheet and select the specified columns
    xls = pd.ExcelFile(file_path)

    for sheet_name in xls.sheet_names:
        sheet_df = xls.parse(sheet_name)
        
        # Check if all columns in columns_to_keep are present in the sheet
        if all(col in sheet_df.columns for col in columns_to_keep):
            # Select and reorder columns as needed
            sheet_df = sheet_df[columns_to_keep]
            
            # Append the sheet data to the list
            dfs.append(sheet_df)

    # Concatenate all DataFrames in the list into one
    combined_df = pd.concat(dfs, ignore_index=True)

    # Replace 'Combined' with the name of your combined sheet
    combined_df.to_excel('/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/Combined_13_SPRPdistricts.xlsx', index=False)


def combine_excel_sheets():
    # Replace these with your file paths
    file1_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/17Combined.xlsx'
    file2_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/Combined_13_SPRPdistricts.xlsx'
    output_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/combined_all.xlsx'

    # Read both Excel files
    df1 = pd.read_excel(file1_path)
    df2 = pd.read_excel(file2_path)

    # Concatenate them into one DataFrame
    combined_df = pd.concat([df1, df2], ignore_index=True)

    # Save the combined DataFrame to a new Excel file
    combined_df.to_excel(output_path, index=False)


# Function to strip known prefixes
def strip_prefix(phone_number):
    prefixes = ["'", "‘", "0", "250"]
    
    # Ensure the input is a string
    phone_number = str(phone_number)
    
    for prefix in prefixes:
        if phone_number.startswith(prefix):
            phone_number = phone_number[len(prefix):]
    return phone_number


def validate_rwanda_import():
    # Replace these with your file paths
    input_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/combined_all.xlsx'
    output_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/final_to_import.xlsx'
    invalid_output_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/invalid_data.xlsx'

    # Read the Excel file
    df = pd.read_excel(input_path)

    # Apply the strip_prefix function to the 'Telephone' column
    df['Telephone'] = df['Telephone'].apply(strip_prefix)

    # Filter valid rows (phone numbers with exactly 9 digits)
    valid_df = df[df['Telephone'].str.match(r'^\d{9}$')]

    # Filter invalid rows (phone numbers not matching the criteria)
    invalid_df = df[~df['Telephone'].str.match(r'^\d{9}$')]

    # Save the valid and invalid data to separate Excel files
    valid_df.to_excel(output_path, index=False)
    invalid_df.to_excel(invalid_output_path, index=False)


def rename_cells():
    input_path = '/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/final_to_import.xlsx'
    # Read the Excel file into a DataFrame
    df = pd.read_excel(input_path)

    # Create a dictionary to store the count of each cell name in a sector
    cell_name_counts = {}

    # Iterate through the rows of the DataFrame
    for index, row in df.iterrows():
        cell_name = row['Cell']
        sector = row['Sector']
        chw_title = row['CHW Title']

        # Check if the cell name already exists in the current sector
        if sector in cell_name_counts:
            if cell_name in cell_name_counts[sector]:
                cell_name_counts[sector][cell_name] += 1
            else:
                cell_name_counts[sector][cell_name] = 1
        else:
            cell_name_counts[sector] = {cell_name: 1}

        # Rename cells if there are more than 3 with the same name in the same sector
        if cell_name_counts[sector][cell_name] > 2:
            if chw_title == 'CHW Chair':
                df.at[index, 'Cell'] = f"{cell_name}1"
            elif chw_title == 'CHW Vice-Chair':
                df.at[index, 'Cell'] = f"{cell_name}2"

    # Save the modified DataFrame to a new Excel file
    df.to_excel('/Users/abizeyimanavictor/Library/CloudStorage/Dropbox/WorldBank/RBC/Roll Out/indexed_double_cells_final.xlsx', index=False)
