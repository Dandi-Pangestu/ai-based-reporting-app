from mcp.server.fastmcp import FastMCP
import base64
import matplotlib.pyplot as plt
import tempfile
import os
import pandas as pd
import io
import json
from typing import Any

server = FastMCP("Visualization Server")

@server.tool()
async def get_example_base64_image() -> str:
    """
    Generates a simple red circle image and returns it as a base64 encoded string.
    """

    plt.figure(figsize=(2,2))
    plt.plot(0.5, 0.5, 'ro', markersize=40)
    plt.axis('off')
    plt.tight_layout()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        plt.savefig(tmpfile.name, bbox_inches='tight', pad_inches=0)
        plt.close()
        with open(tmpfile.name, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode("utf-8")
        os.unlink(tmpfile.name)
        return f"data:image/png;base64,{img_b64}"
    
@server.tool()
async def generate_chart_visualization(data: Any, chart_type: str, x_column: str, y_column: str, title: str) -> str:
    """
    Generates a chart based on dynamic JSON data structure and returns it as a Base64-encoded image.
    """
    import json as _json
    if isinstance(data, str):
        try:
            parsed = _json.loads(data)
            df = pd.DataFrame(parsed)
        except Exception as e:
            raise ValueError(f"Invalid JSON string: {e}")
    elif isinstance(data, (list, dict)):
        df = pd.DataFrame(data)
    else:
        raise ValueError("Data must be a JSON string, list, or dictionary")

    if x_column not in df.columns or y_column not in df.columns:
        raise ValueError(f"Specified columns '{x_column}' or '{y_column}' not found in the data")

    plt.figure(figsize=(8, 6))

    if chart_type.lower() == "line":
        plt.plot(df[x_column], df[y_column], marker='o', linestyle='-', color='blue')
    elif chart_type.lower() == "bar":
        plt.bar(df[x_column], df[y_column], color='orange')
    elif chart_type.lower() == "scatter":
        plt.scatter(df[x_column], df[y_column], color='green')
    elif chart_type.lower() == "pie":
        if len(df) > 0:
            plt.pie(df[y_column], labels=df[x_column], autopct='%1.1f%%', startangle=90)
            plt.axis('equal')
        else:
            raise ValueError("Pie chart requires at least one row of data")
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    plt.title(title, fontsize=14)

    if chart_type.lower() != "pie":
        plt.xlabel(x_column, fontsize=12)
        plt.ylabel(y_column, fontsize=12)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)

    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    buf.close()

    return f"data:image/png;base64,{img_b64}"

if __name__ == "__main__":
    server.run(transport="stdio")