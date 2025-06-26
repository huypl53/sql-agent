import os
from typing import List, Dict, Union, Tuple, Optional
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
import networkx as nx
from wordcloud import WordCloud
import seaborn as sns
from datetime import datetime


def _save_chart(fig: Figure, chart_type: str) -> str:
    """
    Save the chart to disk and return the absolute path.

    Args:
        fig: matplotlib Figure object
        chart_type: Type of chart being saved

    Returns:
        str: Absolute path to the saved image
    """
    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.getcwd(), "charts")
    os.makedirs(output_dir, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{chart_type}_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)

    # Save the figure
    fig.savefig(filepath, dpi=300, bbox_inches="tight")
    plt.close(fig)

    return os.path.abspath(filepath)


def generate_area_chart(
    x_data: List[Union[str, int, float]],
    y_data: List[Union[int, float]],
    title: str = "Area Chart",
    x_label: str = "X Axis",
    y_label: str = "Y Axis",
    color: str = "skyblue",
) -> str:
    """
    Generate an area chart.

    Args:
        x_data: List of x-axis values
        y_data: List of y-axis values
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        color: Area fill color

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.fill_between(x_data, y_data, color=color, alpha=0.4)
    ax.plot(x_data, y_data, color=color, linewidth=2)

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.7)

    return _save_chart(fig, "area_chart")


def generate_bar_chart(
    categories: List[str],
    values: List[Union[int, float]],
    title: str = "Bar Chart",
    x_label: str = "Categories",
    y_label: str = "Values",
    color: str = "royalblue",
) -> str:
    """
    Generate a bar chart.

    Args:
        categories: List of category names
        values: List of corresponding values
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        color: Bar color

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(categories, values, color=color)

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.1f}",
            ha="center",
            va="bottom",
        )

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.7)

    return _save_chart(fig, "bar_chart")


def generate_column_chart(
    categories: List[str],
    values: List[Union[int, float]],
    title: str = "Column Chart",
    x_label: str = "Categories",
    y_label: str = "Values",
    color: str = "forestgreen",
) -> str:
    """
    Generate a column chart (horizontal bar chart).

    Args:
        categories: List of category names
        values: List of corresponding values
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        color: Bar color

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(categories, values, color=color)

    # Add value labels at the end of bars
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width,
            bar.get_y() + bar.get_height() / 2.0,
            f"{width:.1f}",
            ha="left",
            va="center",
        )

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.7)

    return _save_chart(fig, "column_chart")


def generate_dual_axes_chart(
    x_data: List[Union[str, int, float]],
    y1_data: List[Union[int, float]],
    y2_data: List[Union[int, float]],
    y1_label: str = "Primary Axis",
    y2_label: str = "Secondary Axis",
    title: str = "Dual Axes Chart",
    x_label: str = "X Axis",
) -> str:
    """
    Generate a dual-axes chart.

    Args:
        x_data: List of x-axis values
        y1_data: List of primary y-axis values
        y2_data: List of secondary y-axis values
        y1_label: Primary y-axis label
        y2_label: Secondary y-axis label
        title: Chart title
        x_label: X-axis label

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot first dataset
    color1 = "tab:blue"
    ax1.set_xlabel(x_label)
    ax1.set_ylabel(y1_label, color=color1)
    line1 = ax1.plot(x_data, y1_data, color=color1, label=y1_label)
    ax1.tick_params(axis="y", labelcolor=color1)

    # Create second y-axis
    ax2 = ax1.twinx()
    color2 = "tab:red"
    ax2.set_ylabel(y2_label, color=color2)
    line2 = ax2.plot(x_data, y2_data, color=color2, label=y2_label)
    ax2.tick_params(axis="y", labelcolor=color2)

    # Add legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right")

    plt.title(title)

    return _save_chart(fig, "dual_axes_chart")


def generate_histogram_chart(
    data: List[Union[int, float]],
    bins: int = 10,
    title: str = "Histogram",
    x_label: str = "Values",
    y_label: str = "Frequency",
    color: str = "steelblue",
) -> str:
    """
    Generate a histogram chart.

    Args:
        data: List of numerical values
        bins: Number of bins
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        color: Bar color

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(data, bins=bins, color=color, edgecolor="black")

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.7)

    return _save_chart(fig, "histogram_chart")


def generate_line_chart(
    x_data: List[Union[str, int, float]],
    y_data: List[Union[int, float]],
    title: str = "Line Chart",
    x_label: str = "X Axis",
    y_label: str = "Y Axis",
    color: str = "crimson",
    marker: str = "o",
) -> str:
    """
    Generate a line chart.

    Args:
        x_data: List of x-axis values
        y_data: List of y-axis values
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        color: Line color
        marker: Point marker style

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x_data, y_data, color=color, marker=marker, linewidth=2)

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.7)

    return _save_chart(fig, "line_chart")


def generate_pie_chart(
    labels: List[str],
    values: List[Union[int, float]],
    title: str = "Pie Chart",
    colors: Optional[List[str]] = None,
) -> str:
    """
    Generate a pie chart.

    Args:
        labels: List of category labels
        values: List of corresponding values
        title: Chart title
        colors: List of colors for each slice

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        shadow=True,
        startangle=90,
    )
    ax.axis("equal")  # Equal aspect ratio ensures that pie is drawn as a circle
    plt.title(title)

    return _save_chart(fig, "pie_chart")


def generate_radar_chart(
    categories: List[str], values: List[Union[int, float]], title: str = "Radar Chart"
) -> str:
    """
    Generate a radar chart.

    Args:
        categories: List of category names
        values: List of corresponding values
        title: Chart title

    Returns:
        str: Absolute path to the saved image
    """
    # Number of variables
    N = len(categories)

    # Compute angle for each axis
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # Close the loop

    # Add the first value to close the loop
    values = values + values[:1]

    fig, ax = plt.subplots(figsize=(10, 6), subplot_kw=dict(projection="polar"))
    ax.plot(angles, values, linewidth=2, linestyle="solid")
    ax.fill(angles, values, alpha=0.25)

    # Set category labels
    plt.xticks(angles[:-1], categories)

    # Set title
    plt.title(title)

    return _save_chart(fig, "radar_chart")


def generate_scatter_chart(
    x_data: List[Union[int, float]],
    y_data: List[Union[int, float]],
    title: str = "Scatter Chart",
    x_label: str = "X Axis",
    y_label: str = "Y Axis",
    color: str = "purple",
    size: int = 100,
) -> str:
    """
    Generate a scatter chart.

    Args:
        x_data: List of x-axis values
        y_data: List of y-axis values
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        color: Point color
        size: Point size

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(x_data, y_data, c=color, s=size, alpha=0.6)

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.7)

    return _save_chart(fig, "scatter_chart")


def generate_treemap_chart(
    labels: List[str], values: List[Union[int, float]], title: str = "Treemap Chart"
) -> str:
    """
    Generate a treemap chart.

    Args:
        labels: List of category labels
        values: List of corresponding values
        title: Chart title

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    squarify.plot(sizes=values, label=labels, alpha=0.8)
    plt.title(title)

    return _save_chart(fig, "treemap_chart")


def generate_word_cloud_chart(
    text: str,
    title: str = "Word Cloud",
    max_words: int = 100,
    background_color: str = "white",
) -> str:
    """
    Generate a word cloud chart.

    Args:
        text: Input text to generate word cloud
        title: Chart title
        max_words: Maximum number of words to display
        background_color: Background color

    Returns:
        str: Absolute path to the saved image
    """
    wordcloud = WordCloud(
        max_words=max_words, background_color=background_color, width=800, height=400
    ).generate(text)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    plt.title(title)

    return _save_chart(fig, "word_cloud_chart")


def generate_network_graph(
    nodes: List[str],
    edges: List[Tuple[str, str]],
    title: str = "Network Graph",
    node_color: str = "lightblue",
    edge_color: str = "gray",
) -> str:
    """
    Generate a network graph.

    Args:
        nodes: List of node names
        edges: List of tuples representing edges (node1, node2)
        title: Chart title
        node_color: Color of nodes
        edge_color: Color of edges

    Returns:
        str: Absolute path to the saved image
    """
    G = nx.Graph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)

    fig, ax = plt.subplots(figsize=(10, 6))
    pos = nx.spring_layout(G)

    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color=node_color,
        edge_color=edge_color,
        node_size=1000,
        font_size=10,
        font_weight="bold",
    )

    plt.title(title)

    return _save_chart(fig, "network_graph")


def generate_flow_diagram(
    nodes: List[str],
    edges: List[Tuple[str, str]],
    title: str = "Flow Diagram",
    node_color: str = "lightgreen",
    edge_color: str = "gray",
) -> str:
    """
    Generate a flow diagram.

    Args:
        nodes: List of node names
        edges: List of tuples representing edges (node1, node2)
        title: Chart title
        node_color: Color of nodes
        edge_color: Color of edges

    Returns:
        str: Absolute path to the saved image
    """
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)

    fig, ax = plt.subplots(figsize=(10, 6))
    pos = nx.spring_layout(G)

    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color=node_color,
        edge_color=edge_color,
        node_size=1000,
        font_size=10,
        font_weight="bold",
        arrows=True,
    )

    plt.title(title)

    return _save_chart(fig, "flow_diagram")


def generate_fishbone_diagram(
    main_cause: str,
    categories: List[str],
    sub_causes: Dict[str, List[str]],
    title: str = "Fishbone Diagram",
) -> str:
    """
    Generate a fishbone diagram.

    Args:
        main_cause: Main cause/effect
        categories: List of main categories
        sub_causes: Dictionary mapping categories to their sub-causes
        title: Chart title

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(12, 8))

    # Draw main line
    ax.plot([0, 1], [0.5, 0.5], "k-", linewidth=2)

    # Draw main cause
    ax.text(
        1.05, 0.5, main_cause, ha="left", va="center", fontsize=12, fontweight="bold"
    )

    # Draw categories and sub-causes
    for i, category in enumerate(categories):
        y_pos = 0.5 + (i - len(categories) / 2) * 0.2
        ax.plot([0.5, 0.7], [0.5, y_pos], "k-", linewidth=1)
        ax.text(0.7, y_pos, category, ha="left", va="center", fontsize=10)

        # Draw sub-causes
        if category in sub_causes:
            for j, sub_cause in enumerate(sub_causes[category]):
                x_pos = 0.7 + (j + 1) * 0.1
                ax.plot([0.7, x_pos], [y_pos, y_pos], "k-", linewidth=1)
                ax.text(x_pos, y_pos, sub_cause, ha="left", va="center", fontsize=8)

    ax.set_xlim(0, 1.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    plt.title(title)

    return _save_chart(fig, "fishbone_diagram")


def generate_mind_map(
    central_topic: str,
    main_topics: List[str],
    subtopics: Dict[str, List[str]],
    title: str = "Mind Map",
) -> str:
    """
    Generate a mind map.

    Args:
        central_topic: Central topic
        main_topics: List of main topics
        subtopics: Dictionary mapping main topics to their subtopics
        title: Chart title

    Returns:
        str: Absolute path to the saved image
    """
    fig, ax = plt.subplots(figsize=(12, 8))

    # Draw central topic
    ax.text(
        0.5,
        0.5,
        central_topic,
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        bbox=dict(facecolor="lightblue", alpha=0.5),
    )

    # Draw main topics and subtopics
    for i, topic in enumerate(main_topics):
        angle = 2 * np.pi * i / len(main_topics)
        x = 0.5 + 0.3 * np.cos(angle)
        y = 0.5 + 0.3 * np.sin(angle)

        # Draw line to main topic
        ax.plot([0.5, x], [0.5, y], "k-", linewidth=1)

        # Draw main topic
        ax.text(
            x,
            y,
            topic,
            ha="center",
            va="center",
            fontsize=12,
            bbox=dict(facecolor="lightgreen", alpha=0.5),
        )

        # Draw subtopics
        if topic in subtopics:
            for j, subtopic in enumerate(subtopics[topic]):
                sub_angle = angle + (j - len(subtopics[topic]) / 2) * 0.2
                sub_x = x + 0.2 * np.cos(sub_angle)
                sub_y = y + 0.2 * np.sin(sub_angle)

                # Draw line to subtopic
                ax.plot([x, sub_x], [y, sub_y], "k-", linewidth=1)

                # Draw subtopic
                ax.text(
                    sub_x,
                    sub_y,
                    subtopic,
                    ha="center",
                    va="center",
                    fontsize=10,
                    bbox=dict(facecolor="lightyellow", alpha=0.5),
                )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    plt.title(title)

    return _save_chart(fig, "mind_map")
