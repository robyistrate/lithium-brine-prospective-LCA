# lithium-brine-prospective-LCA


Description
-----------
Repository to share the data and code associated with the scientific article **Istrate et al. Climate and water scarcity impacts of global expansion in lithium production from brine** (submitted to journal). The repository contains data files and code to create prospective life cycle inventory (LCI) databases that implement future scenarios for battery-grade lithium carbonate production from brines. The prospective LCI databases combine site-specific LCIs for lithium production projects with site-specific production timelines from the S&P Capital IQ Pro database, IEA projections for electricity mixes in Chile and Argentina, and global projections from the Integrated Assessment Model REMIND.


Bottom-up lithium supply scenarios
------------------------

The future litihum supply scenarios are built with a bottom-up approach that consider site-specific production timelines sourced from the S&P Global database. The [minerals_supply_scenarios](https://github.com/robyistrate/minerals_supply_scenarios) tool was designed specifically to streamline the process of importing, processing, and analyzing mining asset data from the S&P Capital IQ Pro database. The tool provides functionalities to export the resulting scenarios in a format that can be used directly with the [premise tool](https://github.com/polca/premise) for conducting prospective life cycle assessments. The raw dataset from the S&P database needs to be downloaded provided a licence is available and used following the instructions in [minerals_supply_scenarios](https://github.com/robyistrate/minerals_supply_scenarios)

Ecoinvent database compatibility
--------------------------------

ecoinvent 3.10 cut-off

IAM scenario compatibility
---------------------------
The [premise tool](https://github.com/polca/premise) is used to integrate the lithium supply scenarios together with IEA electricity scenarios, and REMIND scenarios. The following coupling is done:

| IAM scenario           | IEA scenario | Lithium senario   |
|------------------------|--------------|-------------------|
| REMIND SSP2-NDC        | STEPS	    | Baseline          |
| REMIND SSP2-NDC        | STEPS        | Ambitious         |
| REMIND SSP2-NDC        | STEPS        | Very ambitious    |
| REMIND SSP2-PkBudg1150 | APS	        | Baseline          |
| REMIND SSP2-PkBudg1150 | APS          | Ambitious         |
| REMIND SSP2-PkBudg1150 | APS          | Very ambitious    |


How to use it?
--------------
Run the notebooks in the indicated order

Authors
--------------
- [Robert Istrate](https://github.com/robyistrate)
- [Vanessa Schenker](https://github.com/schvanes)