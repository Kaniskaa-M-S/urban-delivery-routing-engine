# Urban Delivery Routing Engine

A computational framework for multimodal last-mile delivery routing optimization, 
combining genetic algorithms, demand modeling, and urban network analysis.

## Overview

This project models and compares the operational performance of three last-mile 
delivery modes — cargo bikes, electric vans, and trucks — across urban delivery 
zones using real road network data. The framework evaluates routing efficiency, 
demand scaling behavior, and geographic service feasibility.

## Notebooks

| Notebook | Description |
|----------|-------------|
| 01_exp_setup | Environment setup, network data loading, dispatch zone configuration |
| 02_cargo_bike_routing | Cargo bike route generation and feasibility analysis |
| 03_multimodal_routing | Comparative routing across cargo bike, e-van, and truck modes |
| 04_BREAKPOINT_ANALYSIS | Demand curve modeling and performance breakpoint detection |
| 05_DESTINATION_TYPE_ANALYSIS | Geographic service analysis by destination category |

## Project Structure
```
src/
├── model/        # Mode parameters, feasibility, metrics, scenario manager
├── routing/      # Graph construction, routing engine, route objects  
├── run/          # Batch runners, spatial scenario builders, sensitivity analysis
├── io/           # Data loaders
└── config/       # Path configuration
```

## Methods

- Genetic algorithm with tournament selection and OX1 crossover for route optimization
- Distance matrix precomputation for computational efficiency
- Demand scaling analysis across multiple stop counts
- Geographic feasibility modeling using OSMnx road network data
- Breakpoint curve analysis to identify mode performance thresholds

## Tech Stack

Python · Jupyter · GeoPandas · OSMnx · NetworkX · Shapely · Matplotlib · Folium

## Data

Road network data is retrieved via OSMnx. Demand and destination data represent 
delivery zones across urban dispatch areas. Raw data files are not included. 
Run `01_exp_setup.ipynb` to initialize the network data pipeline.

## Status

Active research project. Analysis ongoing.

