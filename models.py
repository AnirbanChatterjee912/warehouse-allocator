"""
models.py
---------
SQLAlchemy ORM models for the Smart Warehouse Storage Allocation System.

Tables:
    Dataset          -> one row per uploaded .txt file
    Product          -> parsed product rows belonging to a Dataset
    Rack             -> warehouse rack configuration
    AllocationRun    -> one row per "Run Allocation" click (dataset + algorithm)
    AllocationResult -> per-product outcome of a specific AllocationRun
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Dataset(db.Model):
    """Represents a single uploaded dataset (.txt file)."""

    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    product_count = db.Column(db.Integer, default=0)
    valid_row_count = db.Column(db.Integer, default=0)
    error_row_count = db.Column(db.Integer, default=0)

    products = db.relationship("Product", backref="dataset", cascade="all, delete-orphan")
    runs = db.relationship("AllocationRun", backref="dataset", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "upload_time": self.upload_time.strftime("%Y-%m-%d %H:%M:%S") if self.upload_time else None,
            "product_count": self.product_count,
            "valid_row_count": self.valid_row_count,
            "error_row_count": self.error_row_count,
        }


class Product(db.Model):
    """A single validated product line parsed from a dataset."""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False)

    product_id = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    length = db.Column(db.Float, nullable=False)
    width = db.Column(db.Float, nullable=False)
    height = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    storage_type = db.Column(db.String(20), nullable=False)
    fragile = db.Column(db.String(5), nullable=False)
    temperature_requirement = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    @property
    def unit_volume(self):
        return self.length * self.width * self.height

    @property
    def total_volume(self):
        return self.unit_volume * self.quantity

    @property
    def total_weight(self):
        return self.weight * self.quantity

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "weight": self.weight,
            "priority": self.priority,
            "storage_type": self.storage_type,
            "fragile": self.fragile,
            "temperature_requirement": self.temperature_requirement,
            "quantity": self.quantity,
            "unit_volume": round(self.unit_volume, 2),
            "total_volume": round(self.total_volume, 2),
            "total_weight": round(self.total_weight, 2),
        }


class Rack(db.Model):
    """Warehouse storage rack configuration."""

    __tablename__ = "racks"

    id = db.Column(db.Integer, primary_key=True)
    rack_id = db.Column(db.String(50), nullable=False, unique=True)
    length = db.Column(db.Float, nullable=False)
    width = db.Column(db.Float, nullable=False)
    height = db.Column(db.Float, nullable=False)
    max_weight = db.Column(db.Float, nullable=False)
    rack_type = db.Column(db.String(20), nullable=False, default="Normal")
    active = db.Column(db.Boolean, default=True)

    @property
    def volume(self):
        return self.length * self.width * self.height

    def to_dict(self):
        return {
            "id": self.id,
            "rack_id": self.rack_id,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "max_weight": self.max_weight,
            "rack_type": self.rack_type,
            "volume": round(self.volume, 2),
            "active": self.active,
        }


class AllocationRun(db.Model):
    """One execution of an allocation algorithm against a dataset."""

    __tablename__ = "allocation_runs"

    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False)
    algorithm = db.Column(db.String(50), nullable=False)
    run_time = db.Column(db.DateTime, default=datetime.utcnow)

    total_volume = db.Column(db.Float, default=0)
    occupied_volume = db.Column(db.Float, default=0)
    unused_volume = db.Column(db.Float, default=0)
    space_utilization = db.Column(db.Float, default=0)
    avg_rack_utilization = db.Column(db.Float, default=0)
    weight_utilization = db.Column(db.Float, default=0)
    priority_score = db.Column(db.Float, default=0)
    allocated_products = db.Column(db.Integer, default=0)
    unallocated_products = db.Column(db.Integer, default=0)

    results = db.relationship("AllocationResult", backref="run", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "algorithm": self.algorithm,
            "run_time": self.run_time.strftime("%Y-%m-%d %H:%M:%S") if self.run_time else None,
            "total_volume": round(self.total_volume, 2),
            "occupied_volume": round(self.occupied_volume, 2),
            "unused_volume": round(self.unused_volume, 2),
            "space_utilization": round(self.space_utilization, 2),
            "avg_rack_utilization": round(self.avg_rack_utilization, 2),
            "weight_utilization": round(self.weight_utilization, 2),
            "priority_score": round(self.priority_score, 2),
            "allocated_products": self.allocated_products,
            "unallocated_products": self.unallocated_products,
        }


class AllocationResult(db.Model):
    """Per-product outcome (which rack, how much quantity) for a given run."""

    __tablename__ = "allocation_results"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("allocation_runs.id"), nullable=False)

    product_id = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    rack_id = db.Column(db.String(50), nullable=True)  # null if fully unallocated
    allocated_quantity = db.Column(db.Integer, default=0)
    total_quantity = db.Column(db.Integer, default=0)
    allocated_volume = db.Column(db.Float, default=0)
    allocated_weight = db.Column(db.Float, default=0)
    priority = db.Column(db.String(20), nullable=False)
    storage_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="Unallocated")  # Allocated / Partial / Unallocated

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "rack_id": self.rack_id,
            "allocated_quantity": self.allocated_quantity,
            "total_quantity": self.total_quantity,
            "allocated_volume": round(self.allocated_volume, 2),
            "allocated_weight": round(self.allocated_weight, 2),
            "priority": self.priority,
            "storage_type": self.storage_type,
            "status": self.status,
        }


def seed_default_racks(app):
    """Populate the racks table with default racks if it is empty."""
    from config import Config

    with app.app_context():
        if Rack.query.count() == 0:
            for rack_data in Config.DEFAULT_RACKS:
                rack = Rack(**rack_data)
                db.session.add(rack)
            db.session.commit()
