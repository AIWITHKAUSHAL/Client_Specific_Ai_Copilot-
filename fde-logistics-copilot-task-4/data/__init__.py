"""Prototype data sources.

The prototype keeps shipment and policy data in-process so the assignment
runs with ``python app.py`` and no database, network or API key.  Every
access goes through the accessor functions in this package, which is the
seam a Forward Deployment Engineer replaces with a client adapter (TMS /
WMS / ERP API, SQL database, document store) during deployment.
"""

from data.policies import POLICIES, get_all_policies, get_policy_record
from data.shipments import SHIPMENTS, get_all_shipments, get_shipment_record

__all__ = [
    "POLICIES",
    "SHIPMENTS",
    "get_all_policies",
    "get_all_shipments",
    "get_policy_record",
    "get_shipment_record",
]
