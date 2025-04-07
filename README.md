# lithium-prospective-scenarios


Description
-----------
This datapackage implements future scenarios for battery-grade lithium carbonate production from brines, 
combining site-specific production timelines from the S&P database with site-specific LCIs, IEA projections for electricity mixes 
in Chile and Argentina and the projections of global models such as REMIND.

Sourced from publication
------------------------

xxxxxxxxxxxx

Ecoinvent database compatibility
--------------------------------

ecoinvent 3.10 cut-off

IAM scenario compatibility
---------------------------

The following coupling is done between lithium supply scenarios, 
IEA electricity scenarios, and IAM scenarios:

| IAM scenario           | IEA scenario | Lithium senario   |
|------------------------|--------------|-------------------|
| REMIND SSP2-NDC        | STEPS	    | Baseline          |
| REMIND SSP2-NDC        | STEPS        | Ambitious         |
| REMIND SSP2-NDC        | STEPS        | Very ambitious    |
| REMIND SSP2-PkBudg1150 | APS	        | Baseline          |
| REMIND SSP2-PkBudg1150 | APS          | Ambitious         |
| REMIND SSP2-PkBudg1150 | APS          | Very ambitious    |

What does this do?
------------------


Lithium
********

The following market is introduced for each lithium brine production country:

* `market for lithium carbonate, from brines (S&P)`

And the following technologies feed into it:

xxxxxxxxxxxx


Flow diagram
------------


How to use it?
--------------
Run the notebooks
