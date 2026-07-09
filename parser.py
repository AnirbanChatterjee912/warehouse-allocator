"""
parser.py
---------
Parses and validates the uploaded .txt product dataset.

Expected comma separated row format (11 fields):
    Product ID, Product Name, Length, Width, Height, Weight,
    Priority, Storage Type, Fragile(Yes/No), Temperature Requirement, Quantity

Returns a tuple of (valid_products: list[dict], errors: list[dict])
so the caller (Flask route) can show a full validation report instead of
failing on the first bad row.
"""

from config import Config


def _clean(value):
    return value.strip() if isinstance(value, str) else value


def parse_line(line_number, raw_line):
    """
    Validate a single dataset line.
    Returns (product_dict_or_None, error_dict_or_None)
    """
    raw_line = raw_line.strip()
    if not raw_line:
        return None, None  # silently skip blank lines

    if raw_line.startswith("#"):
        return None, None  # allow comment lines

    fields = [f.strip() for f in raw_line.split(",")]

    if len(fields) != Config.EXPECTED_FIELD_COUNT:
        return None, {
            "line": line_number,
            "raw": raw_line,
            "error": f"Expected {Config.EXPECTED_FIELD_COUNT} fields, found {len(fields)}",
        }

    (product_id, product_name, length, width, height, weight,
     priority, storage_type, fragile, temperature_requirement, quantity) = fields

    errors = []

    # --- Product ID ---
    if not product_id:
        errors.append("Product ID is missing")

    # --- Product Name ---
    if not product_name:
        errors.append("Product Name is missing")

    # --- Numeric dimension fields ---
    def parse_positive_float(name, val):
        try:
            f = float(val)
        except (ValueError, TypeError):
            errors.append(f"{name} must be a number (got '{val}')")
            return None
        if f <= 0:
            errors.append(f"{name} must be a positive number (got '{val}')")
            return None
        return f

    length_f = parse_positive_float("Length", length)
    width_f = parse_positive_float("Width", width)
    height_f = parse_positive_float("Height", height)
    weight_f = parse_positive_float("Weight", weight)

    # --- Priority ---
    if priority not in Config.VALID_PRIORITIES:
        errors.append(
            f"Invalid Priority '{priority}' (allowed: {', '.join(Config.VALID_PRIORITIES)})"
        )

    # --- Storage Type ---
    if storage_type not in Config.VALID_STORAGE_TYPES:
        errors.append(
            f"Invalid Storage Type '{storage_type}' (allowed: {', '.join(Config.VALID_STORAGE_TYPES)})"
        )

    # --- Fragile flag ---
    if fragile not in Config.VALID_FRAGILE_FLAGS:
        errors.append(
            f"Invalid Fragile flag '{fragile}' (allowed: {', '.join(Config.VALID_FRAGILE_FLAGS)})"
        )

    # --- Temperature Requirement ---
    if temperature_requirement not in Config.VALID_TEMPERATURE_REQUIREMENTS:
        errors.append(
            f"Invalid Temperature Requirement '{temperature_requirement}' "
            f"(allowed: {', '.join(Config.VALID_TEMPERATURE_REQUIREMENTS)})"
        )

    # --- Quantity ---
    try:
        quantity_i = int(quantity)
        if quantity_i <= 0:
            errors.append(f"Quantity must be a positive integer (got '{quantity}')")
            quantity_i = None
    except (ValueError, TypeError):
        errors.append(f"Quantity must be a positive integer (got '{quantity}')")
        quantity_i = None

    if errors:
        return None, {"line": line_number, "raw": raw_line, "error": "; ".join(errors)}

    product = {
        "product_id": product_id,
        "product_name": product_name,
        "length": length_f,
        "width": width_f,
        "height": height_f,
        "weight": weight_f,
        "priority": priority,
        "storage_type": storage_type,
        "fragile": fragile,
        "temperature_requirement": temperature_requirement,
        "quantity": quantity_i,
    }
    return product, None


def parse_dataset_file(filepath):
    """
    Reads the dataset file line by line, validating each row.
    Also detects duplicate Product IDs across the whole file.

    Returns:
        valid_products (list[dict]), errors (list[dict])
    """
    valid_products = []
    errors = []
    seen_ids = {}

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for idx, raw_line in enumerate(lines, start=1):
        product, error = parse_line(idx, raw_line)
        if error:
            errors.append(error)
            continue
        if product is None:
            continue  # blank/comment line

        pid = product["product_id"]
        if pid in seen_ids:
            errors.append({
                "line": idx,
                "raw": raw_line.strip(),
                "error": f"Duplicate Product ID '{pid}' (first seen on line {seen_ids[pid]})",
            })
            continue

        seen_ids[pid] = idx
        valid_products.append(product)

    return valid_products, errors
