"""
app.py
------
Main Flask application for the Smart Warehouse Storage Allocation System.

Registers:
    - Page routes (Home, Upload, Dashboard, Result, Compare, History)
    - REST API routes (/api/upload, /api/analyze, /api/allocate, /api/history, /api/export)
    - Export endpoints (CSV / PDF)
"""

import os
import io
import csv
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_file, abort
)
from werkzeug.utils import secure_filename

from config import Config
from models import db, Dataset, Product, Rack, AllocationRun, AllocationResult, seed_default_racks
from parser import parse_dataset_file
from allocation import run_allocation, compute_statistics
from optimizer import recommend_strategy

# ReportLab for PDF report generation
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()
    seed_default_racks(app)

    register_page_routes(app)
    register_api_routes(app)

    return app


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )


# ---------------------------------------------------------------------------
# Helper functions shared by page + API routes
# ---------------------------------------------------------------------------

def get_active_racks():
    return Rack.query.filter_by(active=True).order_by(Rack.id.asc()).all()


def dataset_products_as_dicts(dataset_id):
    products = Product.query.filter_by(dataset_id=dataset_id).all()
    return [p.to_dict() for p in products], products


def execute_allocation(dataset_id, algorithm):
    """Shared logic: run an algorithm against a dataset's products and persist the run."""
    products = Product.query.filter_by(dataset_id=dataset_id).all()
    racks = get_active_racks()

    if not products:
        raise ValueError("Dataset has no valid products to allocate.")
    if not racks:
        raise ValueError("No active racks configured in the warehouse.")

    product_dicts = [
        {
            "product_id": p.product_id,
            "product_name": p.product_name,
            "length": p.length,
            "width": p.width,
            "height": p.height,
            "weight": p.weight,
            "priority": p.priority,
            "storage_type": p.storage_type,
            "fragile": p.fragile,
            "temperature_requirement": p.temperature_requirement,
            "quantity": p.quantity,
        }
        for p in products
    ]

    results, rack_states = run_allocation(product_dicts, racks, algorithm)
    stats = compute_statistics(results, rack_states)

    run = AllocationRun(
        dataset_id=dataset_id,
        algorithm=algorithm,
        total_volume=stats["total_volume"],
        occupied_volume=stats["occupied_volume"],
        unused_volume=stats["unused_volume"],
        space_utilization=stats["space_utilization"],
        avg_rack_utilization=stats["avg_rack_utilization"],
        weight_utilization=stats["weight_utilization"],
        priority_score=stats["priority_score"],
        allocated_products=stats["allocated_products"],
        unallocated_products=stats["unallocated_products"],
    )
    db.session.add(run)
    db.session.flush()  # get run.id before commit

    for r in results:
        db.session.add(AllocationResult(
            run_id=run.id,
            product_id=r["product_id"],
            product_name=r["product_name"],
            rack_id=r["rack_id"],
            allocated_quantity=r["allocated_quantity"],
            total_quantity=r["total_quantity"],
            allocated_volume=r["allocated_volume"],
            allocated_weight=r["allocated_weight"],
            priority=r["priority"],
            storage_type=r["storage_type"],
            status=r["status"],
        ))

    db.session.commit()

    rack_state_dicts = [rs.to_dict() for rs in rack_states]
    return run, results, rack_state_dicts, stats


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

def register_page_routes(app):

    @app.route("/")
    def index():
        dataset_count = Dataset.query.count()
        run_count = AllocationRun.query.count()
        rack_count = Rack.query.filter_by(active=True).count()
        latest_run = AllocationRun.query.order_by(AllocationRun.id.desc()).first()
        return render_template(
            "index.html",
            dataset_count=dataset_count,
            run_count=run_count,
            rack_count=rack_count,
            latest_run=latest_run,
            algorithms=Config.ALGORITHMS,
        )

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        racks = Rack.query.order_by(Rack.id.asc()).all()

        if request.method == "POST":
            if "dataset_file" not in request.files:
                flash("No file part in the request.", "danger")
                return redirect(url_for("upload"))

            file = request.files["dataset_file"]
            if file.filename == "":
                flash("No file selected.", "danger")
                return redirect(url_for("upload"))

            if not allowed_file(file.filename):
                flash("Only .txt files are supported.", "danger")
                return redirect(url_for("upload"))

            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            stored_name = f"{timestamp}_{filename}"
            stored_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
            file.save(stored_path)

            valid_products, errors = parse_dataset_file(stored_path)

            dataset = Dataset(
                filename=filename,
                stored_path=stored_path,
                product_count=len(valid_products) + len(errors),
                valid_row_count=len(valid_products),
                error_row_count=len(errors),
            )
            db.session.add(dataset)
            db.session.flush()

            for p in valid_products:
                db.session.add(Product(dataset_id=dataset.id, **p))

            db.session.commit()

            if errors:
                flash(
                    f"Uploaded with {len(errors)} invalid row(s) skipped. "
                    f"{len(valid_products)} valid product(s) imported.",
                    "warning",
                )
            else:
                flash(f"Upload successful. {len(valid_products)} product(s) imported.", "success")

            return redirect(url_for("dashboard", dataset_id=dataset.id))

        return render_template("upload.html", racks=racks, algorithms=Config.ALGORITHMS)

    @app.route("/racks/update", methods=["POST"])
    def update_racks():
        """Update warehouse rack configuration from the Upload page form."""
        rack_ids = request.form.getlist("rack_pk")
        for rack_pk in rack_ids:
            rack = Rack.query.get(int(rack_pk))
            if not rack:
                continue
            rack.length = float(request.form.get(f"length_{rack_pk}", rack.length))
            rack.width = float(request.form.get(f"width_{rack_pk}", rack.width))
            rack.height = float(request.form.get(f"height_{rack_pk}", rack.height))
            rack.max_weight = float(request.form.get(f"max_weight_{rack_pk}", rack.max_weight))
            rack.rack_type = request.form.get(f"rack_type_{rack_pk}", rack.rack_type)
            rack.active = request.form.get(f"active_{rack_pk}") == "on"
        db.session.commit()
        flash("Warehouse configuration updated.", "success")
        return redirect(url_for("upload"))

    @app.route("/dashboard")
    @app.route("/dashboard/<int:dataset_id>")
    def dashboard(dataset_id=None):
        if dataset_id is None:
            dataset = Dataset.query.order_by(Dataset.id.desc()).first()
        else:
            dataset = Dataset.query.get_or_404(dataset_id)

        if dataset is None:
            flash("No dataset uploaded yet. Please upload one first.", "info")
            return redirect(url_for("upload"))

        products, product_objs = dataset_products_as_dicts(dataset.id)
        racks = get_active_racks()
        recommendation = recommend_strategy(products, racks)

        latest_run = (
            AllocationRun.query.filter_by(dataset_id=dataset.id)
            .order_by(AllocationRun.id.desc())
            .first()
        )

        return render_template(
            "dashboard.html",
            dataset=dataset,
            products=products,
            racks=[r.to_dict() for r in racks],
            recommendation=recommendation,
            algorithms=Config.ALGORITHMS,
            latest_run=latest_run,
        )

    @app.route("/allocate/<int:dataset_id>", methods=["POST"])
    def allocate(dataset_id):
        algorithm = request.form.get("algorithm", "first_fit")
        try:
            run, results, rack_states, stats = execute_allocation(dataset_id, algorithm)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("dashboard", dataset_id=dataset_id))

        return redirect(url_for("result", run_id=run.id))

    @app.route("/result/<int:run_id>")
    def result(run_id):
        run = AllocationRun.query.get_or_404(run_id)
        results = AllocationResult.query.filter_by(run_id=run.id).all()
        dataset = Dataset.query.get(run.dataset_id)

        products, _ = dataset_products_as_dicts(dataset.id)
        racks = get_active_racks()
        ai = recommend_strategy(products, racks)

        rack_breakdown = {}
        for r in results:
            rack_breakdown.setdefault(r.rack_id or "Unallocated", []).append(r)

        return render_template(
            "result.html",
            run=run,
            results=results,
            dataset=dataset,
            algorithms=Config.ALGORITHMS,
            rack_breakdown=rack_breakdown,
            ai=ai,
        )

    @app.route("/compare/<int:dataset_id>")
    def compare(dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)
        products, _ = dataset_products_as_dicts(dataset.id)
        racks = get_active_racks()

        comparison = []
        if products and racks:
            for algo_key, algo_name in Config.ALGORITHMS.items():
                results, rack_states = run_allocation(products, racks, algo_key)
                stats = compute_statistics(results, rack_states)
                comparison.append({
                    "algorithm": algo_key,
                    "algorithm_name": algo_name,
                    **stats,
                })

        return render_template(
            "compare.html",
            dataset=dataset,
            comparison=comparison,
            algorithms=Config.ALGORITHMS,
        )

    @app.route("/history")
    def history():
        datasets = Dataset.query.order_by(Dataset.id.desc()).all()
        runs = AllocationRun.query.order_by(AllocationRun.id.desc()).all()
        return render_template(
            "history.html",
            datasets=datasets,
            runs=runs,
            algorithms=Config.ALGORITHMS,
        )

    @app.route("/export/csv/<int:run_id>")
    def export_csv(run_id):
        run = AllocationRun.query.get_or_404(run_id)
        results = AllocationResult.query.filter_by(run_id=run.id).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Product ID", "Product Name", "Assigned Rack", "Allocated Qty",
            "Total Qty", "Allocated Volume", "Allocated Weight", "Priority",
            "Storage Type", "Status"
        ])
        for r in results:
            writer.writerow([
                r.product_id, r.product_name, r.rack_id or "N/A", r.allocated_quantity,
                r.total_quantity, round(r.allocated_volume, 2), round(r.allocated_weight, 2),
                r.priority, r.storage_type, r.status
            ])

        mem = io.BytesIO(output.getvalue().encode("utf-8"))
        mem.seek(0)
        return send_file(
            mem, mimetype="text/csv", as_attachment=True,
            download_name=f"allocation_run_{run_id}.csv"
        )

    @app.route("/export/pdf/<int:run_id>")
    def export_pdf(run_id):
        run = AllocationRun.query.get_or_404(run_id)
        dataset = Dataset.query.get(run.dataset_id)
        results = AllocationResult.query.filter_by(run_id=run.id).all()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle", parent=styles["Title"], textColor=colors.HexColor("#1e3a5f")
        )
        heading_style = ParagraphStyle(
            "HeadingStyle", parent=styles["Heading2"], textColor=colors.HexColor("#2c5282")
        )

        elements = []
        elements.append(Paragraph("Smart Warehouse Storage Allocation Report", title_style))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"Dataset: {dataset.filename}", styles["Normal"]))
        elements.append(Paragraph(f"Algorithm: {Config.ALGORITHMS.get(run.algorithm, run.algorithm)}", styles["Normal"]))
        elements.append(Paragraph(f"Run Time: {run.run_time.strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
        elements.append(Spacer(1, 16))

        elements.append(Paragraph("Optimization Statistics", heading_style))
        stats_table_data = [
            ["Metric", "Value"],
            ["Total Volume (cm3)", f"{run.total_volume:,.2f}"],
            ["Occupied Volume (cm3)", f"{run.occupied_volume:,.2f}"],
            ["Unused Volume (cm3)", f"{run.unused_volume:,.2f}"],
            ["Space Utilization (%)", f"{run.space_utilization:.2f}"],
            ["Average Rack Utilization (%)", f"{run.avg_rack_utilization:.2f}"],
            ["Weight Utilization (%)", f"{run.weight_utilization:.2f}"],
            ["Priority Allocation Score (%)", f"{run.priority_score:.2f}"],
            ["Allocated Products", str(run.allocated_products)],
            ["Unallocated Products", str(run.unallocated_products)],
        ]
        stats_table = Table(stats_table_data, colWidths=[8 * cm, 8 * cm])
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 16))

        elements.append(Paragraph("Rack Assignment Detail", heading_style))
        result_table_data = [["Product ID", "Name", "Rack", "Qty Alloc.", "Total Qty", "Status"]]
        for r in results:
            result_table_data.append([
                r.product_id, r.product_name, r.rack_id or "N/A",
                str(r.allocated_quantity), str(r.total_quantity), r.status
            ])
        result_table = Table(result_table_data, colWidths=[2.5 * cm, 4.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
        result_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ]))
        elements.append(result_table)
        elements.append(Spacer(1, 16))

        products, _ = dataset_products_as_dicts(dataset.id)
        racks = get_active_racks()
        ai = recommend_strategy(products, racks)
        elements.append(Paragraph("AI Recommendations", heading_style))
        elements.append(Paragraph(f"Recommended Strategy: {Config.ALGORITHMS.get(ai['recommended_algorithm'], 'N/A')}", styles["Normal"]))
        elements.append(Paragraph(ai["reason"], styles["Normal"]))
        elements.append(Paragraph(f"Expected Utilization: {ai['expected_utilization']}%", styles["Normal"]))
        elements.append(Paragraph(f"Future Prediction: {ai['future_prediction']}", styles["Normal"]))
        for b in ai["bottlenecks"]:
            elements.append(Paragraph(f"- {b}", styles["Normal"]))

        doc.build(elements)
        buffer.seek(0)
        return send_file(
            buffer, mimetype="application/pdf", as_attachment=True,
            download_name=f"allocation_report_{run_id}.pdf"
        )


# ---------------------------------------------------------------------------
# REST API routes
# ---------------------------------------------------------------------------

def register_api_routes(app):

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        if "dataset_file" not in request.files:
            return jsonify({"success": False, "error": "No file part"}), 400

        file = request.files["dataset_file"]
        if file.filename == "" or not allowed_file(file.filename):
            return jsonify({"success": False, "error": "Invalid or missing .txt file"}), 400

        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        stored_name = f"{timestamp}_{filename}"
        stored_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
        file.save(stored_path)

        valid_products, errors = parse_dataset_file(stored_path)

        dataset = Dataset(
            filename=filename,
            stored_path=stored_path,
            product_count=len(valid_products) + len(errors),
            valid_row_count=len(valid_products),
            error_row_count=len(errors),
        )
        db.session.add(dataset)
        db.session.flush()
        for p in valid_products:
            db.session.add(Product(dataset_id=dataset.id, **p))
        db.session.commit()

        return jsonify({
            "success": True,
            "dataset": dataset.to_dict(),
            "errors": errors,
        })

    @app.route("/api/analyze/<int:dataset_id>")
    def api_analyze(dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)
        products, _ = dataset_products_as_dicts(dataset_id)
        racks = get_active_racks()
        recommendation = recommend_strategy(products, racks)
        return jsonify({
            "success": True,
            "dataset": dataset.to_dict(),
            "products": products,
            "recommendation": recommendation,
        })

    @app.route("/api/allocate", methods=["POST"])
    def api_allocate():
        data = request.get_json(force=True, silent=True) or {}
        dataset_id = data.get("dataset_id")
        algorithm = data.get("algorithm", "first_fit")

        if not dataset_id:
            return jsonify({"success": False, "error": "dataset_id is required"}), 400
        if algorithm not in Config.ALGORITHMS:
            return jsonify({"success": False, "error": "Invalid algorithm"}), 400

        try:
            run, results, rack_states, stats = execute_allocation(int(dataset_id), algorithm)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        return jsonify({
            "success": True,
            "run": run.to_dict(),
            "results": results,
            "rack_states": rack_states,
        })

    @app.route("/api/history")
    def api_history():
        runs = AllocationRun.query.order_by(AllocationRun.id.desc()).all()
        return jsonify({"success": True, "runs": [r.to_dict() for r in runs]})

    @app.route("/api/export/<int:run_id>")
    def api_export(run_id):
        run = AllocationRun.query.get_or_404(run_id)
        results = AllocationResult.query.filter_by(run_id=run.id).all()
        return jsonify({
            "success": True,
            "run": run.to_dict(),
            "results": [r.to_dict() for r in results],
        })

    @app.route("/api/racks")
    def api_racks():
        racks = Rack.query.order_by(Rack.id.asc()).all()
        return jsonify({"success": True, "racks": [r.to_dict() for r in racks]})


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
