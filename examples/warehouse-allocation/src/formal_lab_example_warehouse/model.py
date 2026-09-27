"""Warehouse resource allocation model (profile `warehouse_alloc_v1`) — its own payload format, not the neutral IR.

A small distribution warehouse: inbound pallets wait at the docks and are put away into storage zones (bounded
capacity in units); pick stations are assigned to zones (one station per zone, one zone per station); order lines
are picked from a zone that holds the SKU and is served by a station; logical time advances with `tick`.

State locations (paths):
    dock[<inbound>]            units still waiting at the dock (int)
    stock[<zone>,<sku>]        units stored (int)
    serves[<station>]          zone the station serves, or "none"
    picked[<order>,<line>]     line picked (bool)
    done_at[<order>]           logical time the order was completed (0 = open)
    clock                      logical time (int)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROFILE = "warehouse_alloc_v1"
NAMESPACE = "formal-lab.example.warehouse"
SCHEMA_ID = "warehouse-model@1"
SOURCE_FORMAT = "warehouse-json/v1"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Zone(_M):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    capacity: int = Field(ge=1, le=99)
    label: str | None = None


class Station(_M):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str | None = None


class Inbound(_M):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    sku: str
    qty: int = Field(ge=1, le=99)


class Line(_M):
    sku: str
    qty: int = Field(ge=1, le=99)


class Order(_M):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    lines: list[Line] = Field(min_length=1)
    due: int = Field(ge=0)


class StockCell(_M):
    zone: str
    sku: str
    qty: int = Field(ge=0)


class WarehouseModel(_M):
    name: str
    description: str | None = None
    zones: list[Zone] = Field(min_length=1)
    stations: list[Station] = Field(min_length=1)
    skus: list[str] = Field(min_length=1)
    inbound: list[Inbound] = Field(default_factory=list)
    orders: list[Order] = Field(min_length=1)
    initial_stock: list[StockCell] = Field(default_factory=list)
    horizon: int = Field(default=30, ge=1, le=200)
    station_cost: int = Field(default=1, ge=0, description="cost of (re)assigning a station")

    @model_validator(mode="after")
    def _refs(self) -> WarehouseModel:
        zones = {z.id for z in self.zones}
        skus = set(self.skus)
        for ib in self.inbound:
            if ib.sku not in skus:
                raise ValueError(f"inbound {ib.id}: unknown sku {ib.sku!r}")
        for o in self.orders:
            for line in o.lines:
                if line.sku not in skus:
                    raise ValueError(f"order {o.id}: unknown sku {line.sku!r}")
        for cell in self.initial_stock:
            if cell.zone not in zones or cell.sku not in skus:
                raise ValueError(f"initial stock {cell.zone}/{cell.sku} refers to unknown zone or sku")
        ids = [z.id for z in self.zones] + [s.id for s in self.stations] + [i.id for i in self.inbound] + \
            [o.id for o in self.orders]
        if len(set(ids)) != len(ids):
            raise ValueError("zone / station / inbound / order ids must be unique")
        if "none" in zones:
            raise ValueError("'none' is reserved (a station serving no zone)")
        return self


def json_schema() -> dict:
    schema = WarehouseModel.model_json_schema()
    schema["$id"] = f"https://formal-lab.dev/examples/warehouse/{SCHEMA_ID}.schema.json"
    return schema


def demo_model(**overrides) -> WarehouseModel:
    """Two storage zones, one pick station, two SKUs, three inbound pallets, three orders."""
    data = {
        "name": "warehouse-demo",
        "description": "Put inbound pallets away and pick three orders with one pick station",
        "zones": [{"id": "z1", "capacity": 6, "label": "北区"}, {"id": "z2", "capacity": 4, "label": "南区"}],
        "stations": [{"id": "p1", "label": "拣选工位 1"}],
        "skus": ["a", "b"],
        "inbound": [{"id": "in1", "sku": "a", "qty": 3}, {"id": "in2", "sku": "b", "qty": 2},
                    {"id": "in3", "sku": "a", "qty": 2}],
        "orders": [{"id": "o1", "lines": [{"sku": "a", "qty": 2}], "due": 7},
                   {"id": "o2", "lines": [{"sku": "b", "qty": 1}, {"sku": "a", "qty": 1}], "due": 9},
                   {"id": "o3", "lines": [{"sku": "b", "qty": 1}], "due": 10}],
        "horizon": 30,
    }
    data.update(overrides)
    return WarehouseModel.model_validate(data)


def two_station_model() -> WarehouseModel:
    """Two pick stations (for two picking participants that compete for zones)."""
    return demo_model(name="warehouse-two-stations",
                      stations=[{"id": "p1", "label": "拣选工位 1"}, {"id": "p2", "label": "拣选工位 2"}])
