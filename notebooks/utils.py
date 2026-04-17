""""
Functions to create LCI databases and perform LCA results analysis
"""

import bw2calc as bc
import bw2data as bd
import bw2analyzer as bwa
from pathlib import Path
import pandas as pd
from bw2io.utils import activity_hash
import json
from copy import deepcopy
import pycountry
from constructive_geometries import *
import wurst


def create_biosphere_water_regionalized(
        bio_db_name,
        reg_bio_db_name,
        locations,
        **kwargs
):
    """
    This function creates a new biosphere database that contains
    regionalized water flows for use with the AWARE CFs based on a list of locations.

    Only the water flows that are used in the EF3.1 water use method are considered.
    A copy of these flows is created to add irrigation flow.

    From: https://github.com/ecological-systems-design/Geothermal_brines/blob/main/src/BW2_calculations/lci_method_aware.py
    """
    
    if bio_db_name not in bd.databases:
        raise ValueError(f"{bio_db_name} database not found")
    
    # The EF 3.1 water use method implemented in ecoinvent only accounts for
    # emissions of water to air
    bio_acts = [act for act in bd.Database(bio_db_name) 
                if "water" in act['name'].lower() and 'air' in act['categories']]
    
    # combine locations with original water biosphere flows
    biosphere_data = {}
    for bio_act in bio_acts:
        for loc in locations :
            bio_act_data = deepcopy(bio_act.as_dict())
            bio_act_data['location'] = loc  # Add location
            bio_act_data.pop('database')  # Remove database key
            dbname_code = (reg_bio_db_name, activity_hash(bio_act_data))
            biosphere_data[dbname_code] = bio_act_data
    # Add water emission flows for irrigation
    for bio_act in bio_acts:
        for loc in locations:
            bio_act_data = deepcopy(bio_act.as_dict())
            bio_act_data['location'] = loc  # Add location
            bio_act_data.pop('database')  # Remove database key
            bio_act_data['name'] += ', irrigation'
            dbname_code = (reg_bio_db_name, activity_hash(bio_act_data))
            biosphere_data[dbname_code] = bio_act_data

    if reg_bio_db_name in bd.databases:
        del bd.databases[reg_bio_db_name]

    new_bio_db = bd.Database(reg_bio_db_name)
    new_bio_db.write(biosphere_data)
    print(f"{reg_bio_db_name} was created.")


def create_aware_method(
        bio_db_name,
        reg_bio_db_name,
):  
    """
    This function creates the AWARE method with regionalized CFs.

    Annual aggregated characterization factor for:
     1. Agg_CF_irri: agricultural/irrigation water consumption on basin level
     2. Agg_CF_non_irri: all water consumption sectors except irrigation/agriculture on basin level

    It uses the water flows from the standard biosphere database for the world average CF
    and the regionalized water flows for the site-specific CFs

    Agg_CF_non_irri is assumed as the world average characterization factor.

    From: https://github.com/ecological-systems-design/Geothermal_brines/blob/main/src/BW2_calculations/lci_method_aware.py

    """
    # Import biosphere and regionalized biosphere databases
    if bio_db_name not in bd.databases:
        raise ValueError(f"{bio_db_name} database does not exist")
    bio_db = bd.Database(bio_db_name)

    if reg_bio_db_name not in bd.databases:
        raise ValueError(f"{reg_bio_db_name} database does not exist")
    reg_bio_db = bd.Database(reg_bio_db_name)

    # Import regionalized AWARE CFs
    AWARE_CFs_DIR = Path(r"..\inventories\AWARE_regionalized_CFs\AWARE_country_regions_Corrected_online_20230113-1.xlsx")
    cf_aware = pd.read_excel(AWARE_CFs_DIR, engine='openpyxl', sheet_name='AWARE-annual')

    flows_list = []
    unlinked_loc = []

    for flow in reg_bio_db:
        loc_flow = flow.get('location')
        try:
            loc_aware = cf_aware[cf_aware["Ecoinvent_match"] == loc_flow]["Country"].values[0]
        except:
            try:
                # Country name can be identified by ISO2 code
                country_name = pycountry.countries.get(alpha_2=loc_flow).name
                loc_aware = cf_aware[cf_aware["Country"] == country_name]["Country"].values[0]
            except:
                loc_aware = False

        if loc_aware == False:
            if loc_flow not in unlinked_loc :
                unlinked_loc.append(loc_flow)
        else:
            if 'irrigation' in flow.get('name') :
                aware_score = cf_aware.loc[cf_aware.Country == loc_aware, "Agg_CF_irri"].iloc[0]
            else:
                aware_score = cf_aware.loc[cf_aware.Country == loc_aware, "Agg_CF_non_irri"].iloc[0]

            flows_list.append([flow.key, aware_score])

    # Add global average CFs for unspecified
    for flow in bio_db:
        if "water" in flow['name'].lower() and 'air' in flow['categories']:
            aware_score = cf_aware.loc[cf_aware.Ecoinvent_match == "GLO", "Agg_CF_unspecified"].iloc[0]
            flows_list.append([flow.key, aware_score])

    # Write new BW method
    aware_tuple = ('AWARE regionalized', 'Annual', 'All')
    aware_method = bd.Method(aware_tuple)
    aware_method.register()

    # Add metadata
    aware_method.metadata["unit"] = 'm3 world Eq'
    aware_method.metadata["description"] = 'Regionalized CFs from AWARE method'

    aware_method.validate(flows_list)
    aware_method.register()
    aware_method.write(flows_list)
    print("AWARE method created!")


def relink_to_regionalized_water(bio_reg, ds, location):
    """
    Function to link to regionalized water flows within a LCI 
    """
    biosphere = lambda x: x["type"] == "biosphere"

    for exc in filter(biosphere, ds["exchanges"]):
        if "Water" in exc["name"]:
            water_flow = [flow for flow in bio_reg if flow["name"] == exc["name"] 
                          and flow["categories"] == exc["categories"] 
                          and flow["location"] == location]
            if len(water_flow)==0:
                pass
            else:
                exc.update(
                    {"input": water_flow[0].key}
                )


def get_ds_for_location(ds_name, ds_ref_prod, location, DB_NAME):
    """
    This function finds a dataset for the given location or closer
    """
    geomatcher = Geomatcher() # Initialize the geomatcher object   
    possible_datasets = [ds for ds in bd.Database(DB_NAME)
                         if ds["name"]==ds_name
                         and ds["reference product"]==ds_ref_prod]
    
    # Check if there is an exact match for the location
    match_dataset = [ds for ds in possible_datasets if ds['location'] == location]
    if len(match_dataset) == 0:
        # If there is no specific dataset for the location, search for the supraregional locations
        loc_intersection = geomatcher.intersects(location, biggest_first=False)
        
        for loc in [i[1] if type(i)==tuple else i for i in loc_intersection]:
            match_dataset = [ds for ds in possible_datasets if ds['location'] == loc]
            if len(match_dataset) > 0:
                break
            else:
                match_dataset = [ds for ds in possible_datasets if ds['location'] == 'RoW']
    return match_dataset


def create_electric_boiler_activity(actv_name, location, database_name, electricity_source):
    """
    This function creates a simple LCI for an electric industrial boiler for heat supply.

    Description: "Electric boilers are a commercialized technology that pass an electric current through 
    the water between electrodes (electrode boilers) or through immersed heating elements (electric resistance boilers) 
    to produce steam and hot water. While electrode boilers tend to have higher maximum capacities, up to 335 MMBtu/hr, 
    than electric resistance boilers, the efficiencies of both electric boilers are nearly 100%" 
    (Schoeneberger et al 2022 - Advances in Applied Energy 5, 100089)

    Electric boiler efficiency: 99% (Schoeneberger et al 2022 - Advances in Applied Energy 5, 100089)

    The process contains only the input electricity adapted to the electricity source of each site.
    Water consumption and water loss are assumed negligible due to closed system
    """
    BOILER_EFFICIENCY = 0.99
    electricity_amount = (1 / BOILER_EFFICIENCY) / 3.6 # kWh electricity/MJ heat output
    
    # Create activity dictionary
    boiler_dict = {
        'name': actv_name,
        'reference product': "heat, central or small-scale, other than natural gas",
        'location': location,
        'production amount': 1,
        'unit': "megajoule",
        'database': database_name,
        'code': wurst.filesystem.get_uuid()
    }

    # Add exchanges
    exchanges = []
    
    # Add production to exchanges
    exchanges.append({
        'name': boiler_dict['name'],
        'product': boiler_dict['reference product'],
        'location': boiler_dict['location'],
        'amount': boiler_dict['production amount'],
        'unit': boiler_dict['unit'],
        'database': boiler_dict['database'],
        'type': 'production',
        "input": (boiler_dict["database"], boiler_dict["code"])
    })

    # Add technosphere exchanges (only electricity)

    # Diesel generator has MJ diesel burned as unit.
    # Convert kWh electricity to MJ diesel assuming the efficiency
    DIESEL_GENERATOR_EFFICIENCY = 0.4
    if electricity_source["name"] == "diesel, burned in diesel-electric generating set, 10MW":
        electricity_amount = electricity_amount * 3.6 / DIESEL_GENERATOR_EFFICIENCY

    exchanges.append({
        'name': electricity_source['name'],
        'product': electricity_source['reference product'],
        'location': electricity_source['location'],
        'amount': electricity_amount,
        'unit': electricity_source['unit'],
        'database': electricity_source['database'],
        'type': 'technosphere',
        "input": (electricity_source["database"], electricity_source["code"])
    })
        
    boiler_dict.update({'exchanges': exchanges})
    return boiler_dict


def create_heat_pump_activity(actv_name, location, database_name, electricity_source, ei_db):
    """
    This function creates an LCI for heat supply from heat pump for each project.
    The heat pump LCI is adapted from ecoinvent

    """
    # Get original LCI from ecoinvent
    heat_pump_filter = (
        "heat production, at heat pump 30kW, allocation exergy",
        "heat, central or small-scale, other than natural gas",
        "Europe without Switzerland")
    
    get_heat_pump_ds = [
        ac for ac in bd.Database(ei_db) 
        if ac["name"]==heat_pump_filter[0]
        and ac["reference product"]==heat_pump_filter[1] 
        and ac["location"]==heat_pump_filter[2]][0]
    
    # Create project-specific heat pump activity dictionary
    heat_pump_dict = {
        'name': actv_name,
        'reference product': get_heat_pump_ds["reference product"],
        'location': location,
        'production amount': 1,
        'unit': get_heat_pump_ds["unit"],
        'database': database_name,
        'code': wurst.filesystem.get_uuid()
    }

  # Add exchanges
    exchanges = []

    # Add production to exchanges
    exchanges.append({
        'name': heat_pump_dict['name'],
        'product': heat_pump_dict['reference product'],
        'location': heat_pump_dict['location'],
        'amount': heat_pump_dict['production amount'],
        'unit': heat_pump_dict['unit'],
        'database': heat_pump_dict['database'],
        'type': 'production',
        "input": (heat_pump_dict["database"], heat_pump_dict["code"])
    })

    # Add technosphere and biosphere exchanges
    for ex in get_heat_pump_ds.exchanges():
        if ex["type"] == "production":
            pass
        else:
            exchange = {
                'name': ex["name"],
                'unit': ex["unit"],
                'type': ex["type"],
                'amount': ex["amount"],
            }

            if ex["type"] == "technosphere":
                exchange['product'] = ex.input["reference product"]
                exchange['location'] = ex.input["location"]
                exchange['database'] = ex.input["database"]
                exchange['input'] = (ex.input['database'], ex.input['code'])

                # Switch electricity to project-specific source:
                if ex.input["reference product"]=="electricity, low voltage":
                    
                    # Diesel generator has MJ diesel burned as unit.
                    # Convert kWh electricity to MJ diesel assuming the efficiency
                    DIESEL_GENERATOR_EFFICIENCY = 0.4
                    if electricity_source["name"] == "diesel, burned in diesel-electric generating set, 10MW":
                        electricity_amount = ex["amount"] * 3.6 / DIESEL_GENERATOR_EFFICIENCY
                    else:
                        electricity_amount = ex["amount"] 
                        
                    exchange.update({
                        'name': electricity_source["name"],
                        'product': electricity_source["reference product"],
                        "location": electricity_source["location"],
                        "amount": electricity_amount,
                        "unit": electricity_source['unit'],
                        'input': (electricity_source['database'], electricity_source['code'])
                    })
                
            elif ex["type"] == "biosphere":
                exchange['categories'] = ex.input["categories"]
                exchange['database'] = ex.input["database"]
                exchange['input'] = (ex.input['database'], ex.input['code'])

            exchanges.append(exchange)
    heat_pump_dict.update({"exchanges": exchanges})
    return heat_pump_dict


def populate_prod_pathaways(config_file, var_id, var_lci, var_product, in_ecoinvent, regionalize, new_dataset, var):
    config_file["production pathways"].pop(var_id, None)

    config_file["production pathways"].update({
        var_id: {
            "ecoinvent alias":{
                "exists in original database": in_ecoinvent,
                "name": var_lci,
                "reference product": var_product,
                "regionalize": regionalize,
                "new dataset": new_dataset
            },
            "production volume":{
                "variable": var
            }
        }
    })

def recursive_calculation_cumulative_flows(
        activity,
        foreground_activities,
        amount=1,
        cumulative_flows=None):
    """
    Adapted from https://github.com/brightway-lca/brightway2/blob/master/notebooks/Contribution%20analysis%20and%20comparison.ipynb
    
    This function calculates the required cumulative amounts of each LCI flow within
    the foreground activities. This data will be used to perform process contribution later.

    :activity:
    :foreground_activities: list of foreground activities
    :amount:
    :cumulative_flows:
    """
    if cumulative_flows is None:
        cumulative_flows = {}

    # Creat dictionary of LCI flows with their cumulative amounts
    for exc in activity.exchanges():

        # Avoid double-counting; we only consider input flows from the background system
        if exc.input in foreground_activities:
            continue
        
        exc_amount = exc["amount"] * amount
        if exc.input in cumulative_flows:
            cumulative_flows[exc.input] += exc_amount
        else:
            cumulative_flows[exc.input] = exc_amount

    for actv in activity.technosphere():
        if actv.input in foreground_activities:

            recursive_calculation_cumulative_flows(
                    activity=actv.input,
                    foreground_activities=foreground_activities,
                    amount=amount * actv['amount'],
                    cumulative_flows=cumulative_flows
                    )
    
    return cumulative_flows

def multi_lca(activities, impact_methods_obj):
    calculation_setup = {}
    calculation_setup["inventories"] = {ds["name"] + "|" + ds["reference product"] + "|" + ds["location"]: {ds.id: 1} for ds in activities}
    calculation_setup["methods"] = impact_methods_obj
    data_objs = bd.get_multilca_data_objs(functional_units=calculation_setup["inventories"], 
                                          method_config=calculation_setup["methods"])
    mlca= bc.MultiLCA(demands=calculation_setup["inventories"], 
                      method_config=calculation_setup["methods"], 
                      data_objs=data_objs)
    mlca.lci()
    mlca.lcia()
    return mlca.scores


def get_sensitivity_analysis_data(scenario_file):
    """
    This function reads the data for the sensitivity analysis scenarios from an Excel file and prepares it into a dataframe for being used with presamples.
    Secondly, it adds the bw ids for the involved activities.
    """

    # Import scenario df and remove empty rows
    scenario_data = pd.read_excel(scenario_file).dropna(how="all")
    scenario_label = list(scenario_data.columns)[10:]

    # Map databases codes
    UNIQUE_DBS = pd.concat([scenario_data['to_database'], scenario_data['from_database']]).unique().tolist()
    map_bw_keys =  {}
    for db in UNIQUE_DBS:
        db_obj = bd.Database(db)
        for ds in db_obj:
            if "categories" in ds:
                map_bw_keys[(ds['name'], ds["categories"])] = ds.id
            else:
                map_bw_keys[(ds['reference product'], ds['name'], ds['location'])] = ds.id

    # add the bw code to scenario df (input = process, output = to_process)
    scenario_data["input id"] = None
    scenario_data["output id"] = None
    for index, row in scenario_data.iterrows():
        output_key = (row["to_reference product"], row["to_process"], row["to_location"])

        if row["from_type"] == "technosphere":
            input_key = (row["from_reference_product"], row["from_process"], row["from_location"])
        elif row["from_type"] == "biosphere":
            input_key = (row["from_process"], tuple(row["from_categories"].split('::')))
    
        scenario_data.at[index, "input id"] = map_bw_keys.get(input_key, None)
        scenario_data.at[index, "output id"] = map_bw_keys.get(output_key, None)

    return scenario_label, scenario_data


def run_scenario_lca_matrices(activities, impact_methods_obj, scenario_data_file):
    """
    Run scenario analysis using absolute flows from Excel applied directly to LCI matrices.
    Returns DataFrame: rows = impact categories, columns = scenarios.
    """
    scenario_label, scenario_data = get_sensitivity_analysis_data(scenario_data_file)
    results = {}

    calculation_setup = {}
    calculation_setup["inventories"] = {ds["name"] + "|" + ds["reference product"] + "|" + ds["location"]: {ds.id: 1} for ds in activities}
    calculation_setup["methods"] = impact_methods_obj
    data_objs = bd.get_multilca_data_objs(functional_units=calculation_setup["inventories"], 
                                          method_config=calculation_setup["methods"])
    for scenario_name in scenario_label:
        
        mlca= bc.MultiLCA(demands=calculation_setup["inventories"], 
                          method_config=calculation_setup["methods"],
                          data_objs=data_objs)
        mlca.lci()  # build matrices

        # Apply scenario flows to matrices
        for _, row in scenario_data.iterrows():
            if row['input'] is None or row['output'] is None:
                continue
            amount = row[scenario_name]

            if row['from_type'] == "technosphere":
                row_idx = mlca.technosphere_dict[row['input']]
                col_idx = mlca.activity_dict[row['output']]
                mlca.technosphere_matrix[row_idx, col_idx] = amount
            elif row['from_type'] == "biosphere":
                row_idx = mlca.biosphere_dict[row['input']]
                col_idx = mlca.activity_dict[row['output']]
                mlca.biosphere_matrix[row_idx, col_idx] = amount

        # Redo LCI for updated matrices
        mlca.redo_lci()
        mlca.lcia()
        results[scenario_name] = mlca.scores

    return results

