# [WSL2]
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_api_key
from app.database import get_db
from app.models.incident import BlockedIP


router = APIRouter()


def _node_status(ip: str, blocked_ips: set[str]) -> str:
    return "blocked" if ip in blocked_ips else "normal"


@router.get("/hierarchy", dependencies=[Depends(require_api_key)])
async def get_hierarchy(db: Session = Depends(get_db)):
    blocked = {row.ip_address for row in db.query(BlockedIP.ip_address).all()}

    # Build hierarchy from the 10-host Mininet topology
    hierarchy = {
        "id": "root",
        "label": "Root Node",
        "sublabel": "System Server",
        "level": 0,
        "ip": "10.0.0.1",
        "status": _node_status("10.0.0.1", blocked),
        "children": [
            {
                "id": "admin",
                "label": "Admin Node",
                "sublabel": "IT / Security Ops",
                "level": 1,
                "ip": "10.0.0.2",
                "status": _node_status("10.0.0.2", blocked),
                "children": [
                    {
                        "id": "finance",
                        "label": "Finance Dept",
                        "sublabel": "Hosts 4, 7",
                        "level": 2,
                        "ip": "10.0.1.0/24",
                        "status": "normal",
                        "children": [
                            {
                                "id": "pc-04",
                                "label": "PC-04",
                                "sublabel": "10.0.0.4",
                                "level": 3,
                                "ip": "10.0.0.4",
                                "status": _node_status("10.0.0.4", blocked),
                                "children": [],
                            },
                            {
                                "id": "pc-07",
                                "label": "PC-07",
                                "sublabel": "10.0.0.7",
                                "level": 3,
                                "ip": "10.0.0.7",
                                "status": _node_status("10.0.0.7", blocked),
                                "children": [],
                            },
                        ],
                    },
                    {
                        "id": "dev",
                        "label": "Dev Team",
                        "sublabel": "Hosts 5, 9, 10",
                        "level": 2,
                        "ip": "10.0.2.0/24",
                        "status": "normal",
                        "children": [
                            {
                                "id": "pc-05",
                                "label": "PC-05",
                                "sublabel": "10.0.0.5",
                                "level": 3,
                                "ip": "10.0.0.5",
                                "status": _node_status("10.0.0.5", blocked),
                                "children": [],
                            },
                            {
                                "id": "pc-09",
                                "label": "PC-09",
                                "sublabel": "10.0.0.9",
                                "level": 3,
                                "ip": "10.0.0.9",
                                "status": _node_status("10.0.0.9", blocked),
                                "children": [],
                            },
                            {
                                "id": "pc-10",
                                "label": "PC-10",
                                "sublabel": "10.0.0.10",
                                "level": 3,
                                "ip": "10.0.0.10",
                                "status": _node_status("10.0.0.10", blocked),
                                "children": [],
                            },
                        ],
                    },
                ],
            },
            {
                "id": "db",
                "label": "DB Node",
                "sublabel": "Database Cluster",
                "level": 1,
                "ip": "10.0.0.3",
                "status": _node_status("10.0.0.3", blocked),
                "children": [
                    {
                        "id": "pc-06",
                        "label": "PC-06",
                        "sublabel": "10.0.0.6",
                        "level": 3,
                        "ip": "10.0.0.6",
                        "status": _node_status("10.0.0.6", blocked),
                        "children": [],
                    },
                ],
            },
            {
                "id": "core-services",
                "label": "Core Services",
                "sublabel": "Internal APIs",
                "level": 1,
                "ip": "10.0.0.8",
                "status": _node_status("10.0.0.8", blocked),
                "children": [],
            },
        ],
    }

    return hierarchy
