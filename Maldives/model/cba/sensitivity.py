"""
Sensitivity Analysis
====================

One-way, two-way, and Monte Carlo sensitivity analysis for CBA results.

This module provides:
- One-way sensitivity (tornado diagrams)
- Switching value calculations
- Monte Carlo simulation
- Parameter impact rankings
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
import numpy as np
from copy import deepcopy

from ..config import Config, get_config, SENSITIVITY_PARAMS
from ..scenarios import ScenarioResults
from .npv_calculator import CBACalculator, CBAComparison, NPVResult


@dataclass
class SensitivityParameter:
    """
    Definition of a parameter for sensitivity analysis.
    """
    name: str
    base_value: float
    low_value: float
    high_value: float
    unit: str = ""
    description: str = ""
    
    @property
    def range_pct(self) -> Tuple[float, float]:
        """Return low/high as percentage change from base."""
        low_pct = (self.low_value - self.base_value) / self.base_value * 100 if self.base_value else 0
        high_pct = (self.high_value - self.base_value) / self.base_value * 100 if self.base_value else 0
        return (low_pct, high_pct)


@dataclass
class SensitivityResult:
    """
    Result of one-way sensitivity for a single parameter.
    """
    parameter: str
    base_value: float
    base_npv: float
    
    low_value: float
    low_npv: float
    
    high_value: float
    high_npv: float
    
    # Impact measures
    npv_range: float = 0.0  # |high_npv - low_npv|
    elasticity: float = 0.0  # % change in NPV / % change in parameter
    
    # Note: switching value analysis is implemented separately in
    # run_sensitivity.py:calculate_switching_values() which does scenario-pair
    # comparison and outputs to sensitivity_results.json["switching_values"].


@dataclass
class TornadoData:
    """
    Data for tornado diagram visualization.
    """
    parameters: List[str]
    base_npv: float
    low_npvs: List[float]
    high_npvs: List[float]
    low_values: List[float]
    high_values: List[float]


@dataclass
class MonteCarloResult:
    """
    Results of Monte Carlo simulation.
    """
    n_iterations: int
    npv_mean: float
    npv_std: float
    npv_percentiles: Dict[int, float]  # {5: value, 25: value, 50: value, 75: value, 95: value}
    npv_distribution: List[float]
    
    # Probability metrics
    prob_positive_npv: float
    prob_bcr_greater_1: float
    
    # Value at Risk
    var_5pct: float  # 5th percentile NPV


class SensitivityAnalysis:
    """
    Comprehensive sensitivity analysis for CBA results.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.parameters = self._define_parameters()
    
    def _define_parameters(self) -> Dict[str, SensitivityParameter]:
        """
        Define parameters for sensitivity analysis with their ranges.
        Uses SENSITIVITY_PARAMS populated from parameters.csv.
        """
        params = {}
        sp = SENSITIVITY_PARAMS
        
        # Discount rate
        params["discount_rate"] = SensitivityParameter(
            name="Discount Rate",
            base_value=self.config.economics.discount_rate,
            low_value=sp['discount_rate']['low'],
            high_value=sp['discount_rate']['high'],
            unit="%",
            description="Social discount rate for NPV calculation",
        )
        
        # Diesel price
        params["diesel_price"] = SensitivityParameter(
            name="Diesel Price",
            base_value=self.config.fuel.price_2026,
            low_value=sp['diesel_price']['low'],
            high_value=sp['diesel_price']['high'],
            unit="USD/L",
            description="Base diesel fuel price",
        )
        
        # Diesel escalation
        params["diesel_escalation"] = SensitivityParameter(
            name="Diesel Price Escalation",
            base_value=self.config.fuel.price_escalation,
            low_value=sp['diesel_escalation']['low'],
            high_value=sp['diesel_escalation']['high'],
            unit="%/year",
            description="Annual diesel price increase",
        )
        
        # Solar CAPEX
        params["solar_capex"] = SensitivityParameter(
            name="Solar PV CAPEX",
            base_value=self.config.technology.solar_pv_capex,
            low_value=sp['solar_capex']['low'],
            high_value=sp['solar_capex']['high'],
            unit="USD/kW",
            description="Solar PV installed cost",
        )
        
        # Battery CAPEX
        params["battery_capex"] = SensitivityParameter(
            name="Battery CAPEX",
            base_value=self.config.technology.battery_capex,
            low_value=sp['battery_capex']['low'],
            high_value=sp['battery_capex']['high'],
            unit="USD/kWh",
            description="Battery storage installed cost",
        )
        
        # Cable CAPEX
        params["cable_capex"] = SensitivityParameter(
            name="Undersea Cable CAPEX",
            base_value=self.config.technology.cable_capex_per_km,
            low_value=sp['cable_capex_per_km']['low'],
            high_value=sp['cable_capex_per_km']['high'],
            unit="USD/km",
            description="Undersea cable cost per km",
        )
        
        # PPA price
        params["ppa_price"] = SensitivityParameter(
            name="Import PPA Price",
            base_value=self.config.ppa.import_price_2030,
            low_value=sp['import_price']['low'],
            high_value=sp['import_price']['high'],
            unit="USD/kWh",
            description="Electricity import price",
        )
        
        # Social Cost of Carbon
        params["scc"] = SensitivityParameter(
            name="Social Cost of Carbon",
            base_value=self.config.economics.social_cost_carbon,
            low_value=sp['social_cost_carbon']['low'],
            high_value=sp['social_cost_carbon']['high'],
            unit="USD/tCO2",
            description="Monetized cost of emissions",
        )
        
        # Demand growth
        params["demand_growth"] = SensitivityParameter(
            name="Demand Growth Rate",
            base_value=self.config.demand.growth_rates["status_quo"],
            low_value=sp['demand_growth']['low'],
            high_value=sp['demand_growth']['high'],
            unit="%/year",
            description="Annual demand growth rate",
        )
        
        # Solar capacity factor
        params["solar_cf"] = SensitivityParameter(
            name="Solar Capacity Factor",
            base_value=self.config.technology.solar_pv_capacity_factor,
            low_value=sp['solar_cf']['low'],
            high_value=sp['solar_cf']['high'],
            unit="%",
            description="Solar PV capacity factor",
        )
        
        # GoM cost share for cable
        params["gom_cost_share"] = SensitivityParameter(
            name="GoM Cable Cost Share",
            base_value=self.config.one_grid.gom_share_pct,
            low_value=sp['gom_cost_share']['low'],
            high_value=sp['gom_cost_share']['high'],
            unit="%",
            description="Government of Maldives share of cable costs",
        )
        
        # L2: Cable outage rate
        params["outage_rate"] = SensitivityParameter(
            name="Cable Outage Rate",
            base_value=self.config.cable_outage.outage_rate_per_yr,
            low_value=sp['outage_rate']['low'],
            high_value=sp['outage_rate']['high'],
            unit="events/yr",
            description="Poisson rate of cable outage events per year",
        )
        
        # L2: Idle fleet annual cost
        params["idle_fleet_cost"] = SensitivityParameter(
            name="Idle Fleet Annual Cost",
            base_value=self.config.supply_security.idle_fleet_annual_cost_m,
            low_value=sp['idle_fleet_cost']['low'],
            high_value=sp['idle_fleet_cost']['high'],
            unit="$M/yr",
            description="Annual cost of maintaining idle diesel fleet as backup",
        )
        
        # L8: Price elasticity of demand
        params["price_elasticity"] = SensitivityParameter(
            name="Price Elasticity of Demand",
            base_value=self.config.demand.price_elasticity,
            low_value=sp['price_elasticity']['low'],
            high_value=sp['price_elasticity']['high'],
            unit="ratio",
            description="Demand response to electricity price change (post-cable FI only)",
        )
        
        # L14: Expanded parameters (8 new)
        
        # Health damage cost
        params["health_damage"] = SensitivityParameter(
            name="Health Damage Cost",
            base_value=self.config.economics.health_damage_cost_per_mwh,
            low_value=sp['health_damage']['low'],
            high_value=sp['health_damage']['high'],
            unit="USD/MWh",
            description="Health externality cost per MWh of diesel generation",
        )
        
        # Fuel efficiency
        params["fuel_efficiency"] = SensitivityParameter(
            name="Diesel Fuel Efficiency",
            base_value=self.config.fuel.kwh_per_liter,
            low_value=sp['fuel_efficiency']['low'],
            high_value=sp['fuel_efficiency']['high'],
            unit="kWh/L",
            description="Diesel generator fuel efficiency (affects BAU costs most)",
        )
        
        # Base demand
        params["base_demand"] = SensitivityParameter(
            name="Base Demand 2026",
            base_value=self.config.demand.base_demand_gwh,
            low_value=sp['base_demand']['low'],
            high_value=sp['base_demand']['high'],
            unit="GWh",
            description="Starting electricity demand level",
        )
        
        # Battery storage hours
        params["battery_hours"] = SensitivityParameter(
            name="Battery Storage Hours",
            base_value=self.config.technology.battery_hours,
            low_value=sp['battery_hours']['low'],
            high_value=sp['battery_hours']['high'],
            unit="hours",
            description="Duration of battery storage (affects required MWh)",
        )
        
        # Climate adaptation premium
        params["climate_premium"] = SensitivityParameter(
            name="Climate Adaptation Premium",
            base_value=self.config.technology.climate_adaptation_premium,
            low_value=sp['climate_premium']['low'],
            high_value=sp['climate_premium']['high'],
            unit="%",
            description="CAPEX premium for climate-resilient infrastructure",
        )
        
        # Converter station cost
        params["converter_station"] = SensitivityParameter(
            name="Converter Station Cost/MW",
            base_value=self.config.technology.converter_station_cost_per_mw,
            low_value=sp['converter_station']['low'],
            high_value=sp['converter_station']['high'],
            unit="USD/MW",
            description="VSC-HVDC converter station pair cost (C4)",
        )
        
        # Connection cost per household
        params["connection_cost"] = SensitivityParameter(
            name="Connection Cost/HH",
            base_value=self.config.connection.cost_per_household,
            low_value=sp['connection_cost']['low'],
            high_value=sp['connection_cost']['high'],
            unit="USD/HH",
            description="Last-mile household connection cost (L11)",
        )
        
        # Environmental externality (composite)
        env_base = (self.config.economics.noise_damage_per_mwh
                    + self.config.economics.fuel_spill_risk_per_mwh
                    + self.config.economics.biodiversity_impact_per_mwh)
        params["env_externality"] = SensitivityParameter(
            name="Environmental Externality",
            base_value=env_base,
            low_value=sp['env_externality']['low'],
            high_value=sp['env_externality']['high'],
            unit="USD/MWh",
            description="Total environmental externality (noise + spill + biodiversity) per MWh diesel (L16)",
        )
        
        params["sectoral_residential"] = SensitivityParameter(
            name="Sectoral Split (Residential)",
            base_value=self.config.demand.sectoral_residential,
            low_value=sp['sectoral_residential']['low'],
            high_value=sp['sectoral_residential']['high'],
            unit="fraction",
            description="Residential share of public grid demand (SAARC 2005 Energy Balance)",
        )
        
        # V2b: S5/S6/S7-specific parameters (22 → 34)
        params["lng_capex"] = SensitivityParameter(
            name="LNG CAPEX per MW",
            base_value=self.config.lng.capex_per_mw,
            low_value=sp['lng_capex']['low'],
            high_value=sp['lng_capex']['high'],
            unit="USD/MW",
            description="LNG terminal + CCGT per-MW capital cost (ADB/Mahurkar 2023)",
        )
        
        params["lng_fuel_cost"] = SensitivityParameter(
            name="LNG Fuel Cost",
            base_value=self.config.lng.fuel_cost_per_mwh,
            low_value=sp['lng_fuel_cost']['low'],
            high_value=sp['lng_fuel_cost']['high'],
            unit="USD/MWh",
            description="Delivered LNG fuel cost incl. regasification (IEA 2024; Platts LNG)",
        )
        
        params["lng_fuel_escalation"] = SensitivityParameter(
            name="LNG Fuel Escalation",
            base_value=self.config.lng.fuel_escalation,
            low_value=sp['lng_fuel_escalation']['low'],
            high_value=sp['lng_fuel_escalation']['high'],
            unit="%/yr",
            description="Real annual LNG fuel price escalation (IEA WEO 2024)",
        )
        
        params["lng_emission_factor"] = SensitivityParameter(
            name="LNG Emission Factor",
            base_value=self.config.lng.emission_factor,
            low_value=sp['lng_emission_factor']['low'],
            high_value=sp['lng_emission_factor']['high'],
            unit="kgCO2/kWh",
            description="CO2 emissions per kWh from LNG CCGT (IPCC 2006)",
        )
        
        params["floating_capex_premium"] = SensitivityParameter(
            name="Floating Solar CAPEX Premium",
            base_value=self.config.nearshore.floating_solar_capex_premium,
            low_value=sp['floating_capex_premium']['low'],
            high_value=sp['floating_capex_premium']['high'],
            unit="multiplier",
            description="Floating PV cost multiplier vs ground-mount (IRENA 2020)",
        )
        
        params["floating_solar_mw"] = SensitivityParameter(
            name="Floating Solar MW",
            base_value=self.config.nearshore.floating_solar_mw,
            low_value=sp['floating_solar_mw']['low'],
            high_value=sp['floating_solar_mw']['high'],
            unit="MW",
            description="Floating PV capacity on Malé/Kaafu atoll lagoon",
        )
        
        params["nearshore_solar_mw"] = SensitivityParameter(
            name="Near-Shore Solar MW",
            base_value=self.config.nearshore.nearshore_solar_mw,
            low_value=sp['nearshore_solar_mw']['low'],
            high_value=sp['nearshore_solar_mw']['high'],
            unit="MW",
            description="Solar capacity on uninhabited islands near Malé (GIS analysis)",
        )
        
        params["nearshore_cable_cost"] = SensitivityParameter(
            name="Near-Shore Cable Cost/MW",
            base_value=self.config.nearshore.nearshore_cable_cost_per_mw,
            low_value=sp['nearshore_cable_cost']['low'],
            high_value=sp['nearshore_cable_cost']['high'],
            unit="USD/MW",
            description="Per-MW submarine cable cost for near-shore solar islands",
        )
        
        params["wte_capex"] = SensitivityParameter(
            name="WTE CAPEX per kW",
            base_value=self.config.wte.capex_per_kw,
            low_value=sp['wte_capex']['low'],
            high_value=sp['wte_capex']['high'],
            unit="USD/kW",
            description="Small-scale MSW incineration CAPEX (ICLEI 2021; EIA AEO 2024)",
        )
        
        params["deployment_ramp"] = SensitivityParameter(
            name="Deployment Ramp MW/yr",
            base_value=self.config.green_transition.deployment_ramp_mw_per_year,
            low_value=sp['deployment_ramp']['low'],
            high_value=sp['deployment_ramp']['high'],
            unit="MW/yr",
            description="Max annual solar MW additions on outer islands (logistics constraint)",
        )
        
        params["male_max_re"] = SensitivityParameter(
            name="Malé Max RE Share",
            base_value=self.config.green_transition.male_max_re_share,
            low_value=sp['male_max_re']['low'],
            high_value=sp['male_max_re']['high'],
            unit="fraction",
            description="Greater Malé max achievable RE share (ZNES Flensburg rooftop study)",
        )
        
        params["battery_ratio"] = SensitivityParameter(
            name="Battery Ratio",
            base_value=self.config.green_transition.battery_ratio,
            low_value=sp['battery_ratio']['low'],
            high_value=sp['battery_ratio']['high'],
            unit="MWh/MW",
            description="Battery storage sizing per MW solar (NREL ATB 2024; BNEF 2025)",
        )
        
        # Item-2: 6 additional high-impact parameters
        
        # Demand saturation ceiling (A-M-01)
        if 'demand_saturation' in sp:
            params["demand_saturation"] = SensitivityParameter(
                name="Demand Saturation kWh/cap",
                base_value=self.config.demand.demand_saturation_kwh_per_capita,
                low_value=sp['demand_saturation']['low'],
                high_value=sp['demand_saturation']['high'],
                unit="kWh/cap/yr",
                description="Per-capita demand ceiling — caps exponential growth (IEA WEO 2024)",
            )
        
        # Malé near-term growth rate
        if 'male_growth_near' in sp:
            params["male_growth_near"] = SensitivityParameter(
                name="Malé Near-Term Growth",
                base_value=self.config.demand.male_growth_near_term,
                low_value=sp['male_growth_near']['low'],
                high_value=sp['male_growth_near']['high'],
                unit="%/yr",
                description="Greater Malé near-term demand growth (STELCO Master Plan)",
            )
        
        # PV degradation rate
        if 'pv_degradation' in sp:
            params["pv_degradation"] = SensitivityParameter(
                name="PV Degradation Rate",
                base_value=self.config.technology.solar_pv_degradation,
                low_value=sp['pv_degradation']['low'],
                high_value=sp['pv_degradation']['high'],
                unit="%/yr",
                description="Annual solar PV degradation (Jordan & Kurtz 2013; IRENA RPGC 2024)",
            )
        
        # IDC rate
        if 'idc_rate' in sp:
            params["idc_rate"] = SensitivityParameter(
                name="IDC Rate",
                base_value=self.config.technology.idc_rate,
                low_value=sp['idc_rate']['low'],
                high_value=sp['idc_rate']['high'],
                unit="fraction",
                description="Interest During Construction as fraction of base CAPEX (ADB/IFC norms)",
            )
        
        # LNG plant capacity MW
        if 'lng_capacity_mw' in sp:
            params["lng_capacity_mw"] = SensitivityParameter(
                name="LNG Capacity MW",
                base_value=self.config.lng.plant_capacity_mw,
                low_value=sp['lng_capacity_mw']['low'],
                high_value=sp['lng_capacity_mw']['high'],
                unit="MW",
                description="Gulhifalhu LNG terminal installed capacity (GoM Roadmap 2024)",
            )
        
        # Subsidy per kWh
        if 'subsidy_per_kwh' in sp:
            params["subsidy_per_kwh"] = SensitivityParameter(
                name="Subsidy per kWh",
                base_value=self.config.current_system.current_subsidy_per_kwh,
                low_value=sp['subsidy_per_kwh']['low'],
                high_value=sp['subsidy_per_kwh']['high'],
                unit="USD/kWh",
                description="GoM electricity subsidy per kWh (GoM Budget 2024)",
            )
        
        # P8: Transport electrification parameters
        if 'ev_adoption_midpoint' in sp:
            params["ev_adoption_midpoint"] = SensitivityParameter(
                name="EV Adoption Midpoint Year",
                base_value=float(self.config.transport.ev_adoption_midpoint),
                low_value=sp['ev_adoption_midpoint']['low'],
                high_value=sp['ev_adoption_midpoint']['high'],
                unit="year",
                description="S-curve inflection year for EV adoption (Griliches 1957)",
            )
        
        if 'ev_motorcycle_premium' in sp:
            params["ev_motorcycle_premium"] = SensitivityParameter(
                name="E-Motorcycle Premium",
                base_value=self.config.transport.e_motorcycle_premium_2026,
                low_value=sp['ev_motorcycle_premium']['low'],
                high_value=sp['ev_motorcycle_premium']['high'],
                unit="USD",
                description="Upfront cost premium of e-motorcycle over ICE (IEA GEVO 2024)",
            )
        
        if 'transport_health_damage' in sp:
            params["transport_health_damage"] = SensitivityParameter(
                name="Transport PM2.5 Damage",
                base_value=self.config.transport.pm25_damage_per_vkm,
                low_value=sp['transport_health_damage']['low'],
                high_value=sp['transport_health_damage']['high'],
                unit="USD/vkm",
                description="PM2.5 health damage per ICE vehicle-km (Parry et al. 2014)",
            )
        
        if 'petrol_price' in sp:
            params["petrol_price"] = SensitivityParameter(
                name="Petrol Price 2026",
                base_value=self.config.transport.petrol_price_2026,
                low_value=sp['petrol_price']['low'],
                high_value=sp['petrol_price']['high'],
                unit="USD/L",
                description="Retail petrol price in Maldives (STO 2024)",
            )
        
        return params
    
    def run_one_way(
        self,
        scenario_runner: Callable[[Config], ScenarioResults],
        parameter_name: str,
        base_npv: float,
    ) -> SensitivityResult:
        """
        Run one-way sensitivity analysis for a single parameter.
        
        Args:
            scenario_runner: Function that takes config and returns ScenarioResults
            parameter_name: Name of parameter to vary
            base_npv: Base case NPV for comparison
        
        Returns:
            SensitivityResult with NPVs at low, base, and high values
        """
        param = self.parameters[parameter_name]
        
        # Create modified configs
        config_low = self._modify_config(parameter_name, param.low_value)
        config_high = self._modify_config(parameter_name, param.high_value)
        
        # Run scenarios
        results_low = scenario_runner(config_low)
        results_high = scenario_runner(config_high)
        
        # Calculate NPVs
        # F-01 fix: Use economic cost (financial + emission costs) so SCC
        # parameter variation actually affects the tornado diagram. Without
        # emission costs, SCC has zero impact on pv_total_costs.
        calc_low = CBACalculator(config_low)
        calc_high = CBACalculator(config_high)
        
        npv_result_low = calc_low.calculate_npv(results_low)
        npv_result_high = calc_high.calculate_npv(results_high)
        npv_low = npv_result_low.pv_total_costs + npv_result_low.pv_emission_costs
        npv_high = npv_result_high.pv_total_costs + npv_result_high.pv_emission_costs
        
        # Calculate impact measures
        npv_range = abs(npv_high - npv_low)
        
        # Elasticity
        param_range = param.high_value - param.low_value
        if param.base_value != 0 and param_range != 0:
            param_pct_change = param_range / param.base_value
            npv_pct_change = (npv_high - npv_low) / base_npv if base_npv != 0 else 0
            elasticity = npv_pct_change / param_pct_change
        else:
            elasticity = 0
        
        result = SensitivityResult(
            parameter=parameter_name,
            base_value=param.base_value,
            base_npv=base_npv,
            low_value=param.low_value,
            low_npv=npv_low,
            high_value=param.high_value,
            high_npv=npv_high,
            npv_range=npv_range,
            elasticity=elasticity,
        )
        
        return result
    
    def _modify_config(self, parameter_name: str, value: float) -> Config:
        """
        Create a modified config with the specified parameter value.
        """
        config = deepcopy(self.config)
        
        # Map parameter names to config attributes
        if parameter_name == "discount_rate":
            config.economics.discount_rate = value
        elif parameter_name == "diesel_price":
            config.fuel.price_2026 = value
        elif parameter_name == "diesel_escalation":
            config.fuel.price_escalation = value
        elif parameter_name == "solar_capex":
            config.technology.solar_pv_capex = value
        elif parameter_name == "battery_capex":
            config.technology.battery_capex = value
        elif parameter_name == "cable_capex":
            config.technology.cable_capex_per_km = value
            # CR-01 fix: Recompute cable_capex_total (matches _modify_config_inplace)
            submarine_cable = config.one_grid.cable_length_km * value
            converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            bc = submarine_cable + converter_stations + landing
            idc = bc * config.technology.idc_rate
            config.one_grid.cable_capex_total = bc + idc + config.technology.grid_upgrade_cost
        elif parameter_name == "ppa_price":
            config.ppa.import_price_2030 = value
        elif parameter_name == "scc":
            config.economics.social_cost_carbon = value
        elif parameter_name == "demand_growth":
            # Scale all scenario growth rates proportionally (M-BUG-4 fix)
            # 'value' is the perturbed BAU rate; compute ratio vs BAU base
            base_bau = self.config.demand.growth_rates.get("status_quo", 0.05)
            if base_bau != 0:
                scale = value / base_bau
            else:
                scale = 1.0
            for key in config.demand.growth_rates:
                config.demand.growth_rates[key] = self.config.demand.growth_rates[key] * scale
        elif parameter_name == "solar_cf":
            config.technology.solar_pv_capacity_factor = value
        elif parameter_name == "gom_cost_share":
            config.one_grid.gom_share_pct = value
        elif parameter_name == "outage_rate":
            config.cable_outage.outage_rate_per_yr = value
        elif parameter_name == "idle_fleet_cost":
            config.supply_security.idle_fleet_annual_cost_m = value
        elif parameter_name == "price_elasticity":
            config.demand.price_elasticity = value
        # L14: Expanded parameters
        elif parameter_name == "health_damage":
            config.economics.health_damage_cost_per_mwh = value
        elif parameter_name == "fuel_efficiency":
            config.fuel.kwh_per_liter = value
        elif parameter_name == "base_demand":
            config.demand.base_demand_gwh = value
        elif parameter_name == "battery_hours":
            config.technology.battery_hours = value
        elif parameter_name == "climate_premium":
            config.technology.climate_adaptation_premium = value
        elif parameter_name == "converter_station":
            config.technology.converter_station_cost_per_mw = value
            # Recompute cable_capex_total
            submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
            converter_stations = value * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            base_capex = submarine_cable + converter_stations + landing
            idc = base_capex * config.technology.idc_rate
            config.one_grid.cable_capex_total = base_capex + idc + config.technology.grid_upgrade_cost
        elif parameter_name == "connection_cost":
            config.connection.cost_per_household = value
            config.technology.connection_cost_per_hh = value
        elif parameter_name == "env_externality":
            base_total = (self.config.economics.noise_damage_per_mwh
                         + self.config.economics.fuel_spill_risk_per_mwh
                         + self.config.economics.biodiversity_impact_per_mwh)
            scale = value / base_total if base_total > 0 else 1.0
            config.economics.noise_damage_per_mwh = self.config.economics.noise_damage_per_mwh * scale
            config.economics.fuel_spill_risk_per_mwh = self.config.economics.fuel_spill_risk_per_mwh * scale
            config.economics.biodiversity_impact_per_mwh = self.config.economics.biodiversity_impact_per_mwh * scale
        elif parameter_name == "sectoral_residential":
            config.demand.sectoral_residential = value
            # Redistribute remainder equally between commercial and public
            remainder = 1.0 - value
            config.demand.sectoral_commercial = remainder / 2.0
            config.demand.sectoral_public = remainder / 2.0
        # V2b: S5/S6/S7-specific parameters
        elif parameter_name == "lng_capex":
            config.lng.capex_per_mw = value
        elif parameter_name == "lng_fuel_cost":
            config.lng.fuel_cost_per_mwh = value
        elif parameter_name == "lng_fuel_escalation":
            config.lng.fuel_escalation = value
        elif parameter_name == "lng_emission_factor":
            config.lng.emission_factor = value
        elif parameter_name == "floating_capex_premium":
            config.nearshore.floating_solar_capex_premium = value
        elif parameter_name == "floating_solar_mw":
            config.nearshore.floating_solar_mw = value
        elif parameter_name == "nearshore_solar_mw":
            config.nearshore.nearshore_solar_mw = value
        elif parameter_name == "nearshore_cable_cost":
            config.nearshore.nearshore_cable_cost_per_mw = value
        elif parameter_name == "wte_capex":
            config.wte.capex_per_kw = value
        elif parameter_name == "deployment_ramp":
            config.green_transition.deployment_ramp_mw_per_year = value
        elif parameter_name == "male_max_re":
            config.green_transition.male_max_re_share = value
        elif parameter_name == "battery_ratio":
            config.green_transition.battery_ratio = value
            config.green_transition.islanded_battery_ratio = value
        # Item-2: 6 additional high-impact parameters
        elif parameter_name == "demand_saturation":
            config.demand.demand_saturation_kwh_per_capita = value
        elif parameter_name == "male_growth_near":
            config.demand.male_growth_near_term = value
        elif parameter_name == "pv_degradation":
            config.technology.solar_pv_degradation = value
        elif parameter_name == "idc_rate":
            config.technology.idc_rate = value
            # Recompute cable_capex_total since IDC affects it
            submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
            converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            bc = submarine_cable + converter_stations + landing
            idc = bc * value
            config.one_grid.cable_capex_total = bc + idc + config.technology.grid_upgrade_cost
        elif parameter_name == "lng_capacity_mw":
            config.lng.plant_capacity_mw = value
        elif parameter_name == "subsidy_per_kwh":
            config.current_system.current_subsidy_per_kwh = value
        # P8: Transport electrification parameters
        elif parameter_name == "ev_adoption_midpoint":
            config.transport.ev_adoption_midpoint = int(value)
        elif parameter_name == "ev_motorcycle_premium":
            config.transport.e_motorcycle_premium_2026 = value
        elif parameter_name == "transport_health_damage":
            config.transport.pm25_damage_per_vkm = value
        elif parameter_name == "petrol_price":
            config.transport.petrol_price_2026 = value
        
        return config
    
    def calculate_switching_value(
        self,
        scenario_runner: Callable[[Config], ScenarioResults],
        parameter_name: str,
        target_npv: float = 0,
        incremental: bool = True,
    ) -> Optional[float]:
        """
        Calculate the switching value - parameter value at which NPV = target.
        
        Uses bisection method to find the switching value.
        
        Args:
            scenario_runner: Function that takes config and returns ScenarioResults
            parameter_name: Name of parameter to vary
            target_npv: Target NPV value (default 0 for break-even)
            incremental: If True, compare to baseline scenario
        
        Returns:
            Switching value or None if not found in parameter range
        """
        param = self.parameters[parameter_name]
        
        # Check if target is achievable in range
        config_low = self._modify_config(parameter_name, param.low_value)
        config_high = self._modify_config(parameter_name, param.high_value)
        
        calc_low = CBACalculator(config_low)
        calc_high = CBACalculator(config_high)
        
        results_low = scenario_runner(config_low)
        results_high = scenario_runner(config_high)
        
        npv_result_low = calc_low.calculate_npv(results_low)
        npv_result_high = calc_high.calculate_npv(results_high)
        # F-01 fix: economic cost = financial + emission costs
        npv_low = npv_result_low.pv_total_costs + npv_result_low.pv_emission_costs
        npv_high = npv_result_high.pv_total_costs + npv_result_high.pv_emission_costs
        
        # Check if target is in range
        if not ((npv_low - target_npv) * (npv_high - target_npv) < 0):
            return None  # Target not in range
        
        # Bisection method
        low_val = param.low_value
        high_val = param.high_value
        tolerance = (high_val - low_val) * 0.001  # 0.1% tolerance
        
        max_iterations = 50
        for _ in range(max_iterations):
            mid_val = (low_val + high_val) / 2
            config_mid = self._modify_config(parameter_name, mid_val)
            calc_mid = CBACalculator(config_mid)
            results_mid = scenario_runner(config_mid)
            npv_result_mid = calc_mid.calculate_npv(results_mid)
            npv_mid = npv_result_mid.pv_total_costs + npv_result_mid.pv_emission_costs  # F-01 fix
            
            if abs(npv_mid - target_npv) < tolerance * target_npv or abs(high_val - low_val) < tolerance:
                return mid_val
            
            if (npv_mid - target_npv) * (npv_low - target_npv) < 0:
                high_val = mid_val
                npv_high = npv_mid
            else:
                low_val = mid_val
                npv_low = npv_mid
        
        return (low_val + high_val) / 2
    
    def generate_tornado_data(
        self,
        results: Dict[str, SensitivityResult],
        top_n: int = 10,
    ) -> TornadoData:
        """
        Generate data for tornado diagram.
        
        Args:
            results: Dictionary of SensitivityResult by parameter name
            top_n: Number of top parameters to include
        
        Returns:
            TornadoData for visualization
        """
        # Sort by NPV range (descending)
        sorted_params = sorted(
            results.items(),
            key=lambda x: x[1].npv_range,
            reverse=True,
        )[:top_n]
        
        base_npv = sorted_params[0][1].base_npv if sorted_params else 0
        
        return TornadoData(
            parameters=[p[0] for p in sorted_params],
            base_npv=base_npv,
            low_npvs=[p[1].low_npv for p in sorted_params],
            high_npvs=[p[1].high_npv for p in sorted_params],
            low_values=[p[1].low_value for p in sorted_params],
            high_values=[p[1].high_value for p in sorted_params],
        )
    
    def run_monte_carlo(
        self,
        scenario_runner: Callable[[Config], ScenarioResults],
        n_iterations: int = 1000,
        seed: int = 42,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.
        
        Uses triangular distributions for all parameters.
        
        Args:
            scenario_runner: Function that takes config and returns ScenarioResults
            n_iterations: Number of Monte Carlo iterations
            seed: Random seed for reproducibility
        
        Returns:
            MonteCarloResult with distribution statistics
        """
        np.random.seed(seed)
        
        npv_distribution = []
        bcr_distribution = []
        
        for i in range(n_iterations):
            # Sample parameters from distributions
            config = deepcopy(self.config)
            
            for param_name, param in self.parameters.items():
                # Triangular distribution: (low, mode=base, high)
                sampled_value = np.random.triangular(
                    param.low_value,
                    param.base_value,
                    param.high_value,
                )
                config = self._modify_config_inplace(config, param_name, sampled_value)
            
            # Run scenario and calculate NPV
            try:
                results = scenario_runner(config)
                calc = CBACalculator(config)
                npv_result = calc.calculate_npv(results)
                npv_distribution.append(npv_result.pv_total_costs)
            except (ValueError, KeyError, ZeroDivisionError, AttributeError) as e:
                # D-MO-06/F-MO-02 fix: catch specific exceptions and log
                import logging
                logging.getLogger(__name__).warning(f"MC iteration {i+1} failed: {type(e).__name__}: {e}")
                continue
        
        if not npv_distribution:
            raise ValueError("All Monte Carlo iterations failed")
        
        npv_array = np.array(npv_distribution)
        
        return MonteCarloResult(
            n_iterations=len(npv_distribution),
            npv_mean=float(np.mean(npv_array)),
            npv_std=float(np.std(npv_array)),
            npv_percentiles={
                5: float(np.percentile(npv_array, 5)),
                25: float(np.percentile(npv_array, 25)),
                50: float(np.percentile(npv_array, 50)),
                75: float(np.percentile(npv_array, 75)),
                95: float(np.percentile(npv_array, 95)),
            },
            npv_distribution=npv_distribution,
            prob_positive_npv=float(np.mean(npv_array > 0)),
            prob_bcr_greater_1=0.0,  # Would need BCR calculation
            var_5pct=float(np.percentile(npv_array, 5)),
        )
    
    def _modify_config_inplace(self, config: Config, parameter_name: str, value: float) -> Config:
        """
        Modify config in place (for Monte Carlo efficiency).
        """
        if parameter_name == "discount_rate":
            config.economics.discount_rate = value
        elif parameter_name == "diesel_price":
            config.fuel.price_2026 = value
        elif parameter_name == "diesel_escalation":
            config.fuel.price_escalation = value
        elif parameter_name == "solar_capex":
            config.technology.solar_pv_capex = value
        elif parameter_name == "battery_capex":
            config.technology.battery_capex = value
        elif parameter_name == "cable_capex":
            config.technology.cable_capex_per_km = value
            # Recompute cable_capex_total
            submarine_cable = config.one_grid.cable_length_km * value
            converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            bc = submarine_cable + converter_stations + landing
            idc = bc * config.technology.idc_rate
            config.one_grid.cable_capex_total = bc + idc + config.technology.grid_upgrade_cost
        elif parameter_name == "ppa_price":
            config.ppa.import_price_2030 = value
        elif parameter_name == "scc":
            config.economics.social_cost_carbon = value
        elif parameter_name == "demand_growth":
            # Scale all scenario growth rates proportionally (M-BUG-4 fix)
            base_bau = self.config.demand.growth_rates.get("status_quo", 0.05)
            if base_bau != 0:
                scale = value / base_bau
            else:
                scale = 1.0
            for key in config.demand.growth_rates:
                config.demand.growth_rates[key] = self.config.demand.growth_rates[key] * scale
        elif parameter_name == "solar_cf":
            config.technology.solar_pv_capacity_factor = value
        elif parameter_name == "gom_cost_share":
            config.one_grid.gom_share_pct = value
        elif parameter_name == "outage_rate":
            config.cable_outage.outage_rate_per_yr = value
        elif parameter_name == "idle_fleet_cost":
            config.supply_security.idle_fleet_annual_cost_m = value
        elif parameter_name == "price_elasticity":
            config.demand.price_elasticity = value
        # L14: Expanded parameters
        elif parameter_name == "health_damage":
            config.economics.health_damage_cost_per_mwh = value
        elif parameter_name == "fuel_efficiency":
            config.fuel.kwh_per_liter = value
        elif parameter_name == "base_demand":
            config.demand.base_demand_gwh = value
        elif parameter_name == "battery_hours":
            config.technology.battery_hours = value
        elif parameter_name == "climate_premium":
            config.technology.climate_adaptation_premium = value
        elif parameter_name == "converter_station":
            config.technology.converter_station_cost_per_mw = value
            submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
            converter_stations = value * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            bc = submarine_cable + converter_stations + landing
            idc = bc * config.technology.idc_rate
            config.one_grid.cable_capex_total = bc + idc + config.technology.grid_upgrade_cost
        elif parameter_name == "connection_cost":
            config.connection.cost_per_household = value
            config.technology.connection_cost_per_hh = value
        elif parameter_name == "env_externality":
            base_total = (self.config.economics.noise_damage_per_mwh
                         + self.config.economics.fuel_spill_risk_per_mwh
                         + self.config.economics.biodiversity_impact_per_mwh)
            scale = value / base_total if base_total > 0 else 1.0
            config.economics.noise_damage_per_mwh = self.config.economics.noise_damage_per_mwh * scale
            config.economics.fuel_spill_risk_per_mwh = self.config.economics.fuel_spill_risk_per_mwh * scale
            config.economics.biodiversity_impact_per_mwh = self.config.economics.biodiversity_impact_per_mwh * scale
        elif parameter_name == "sectoral_residential":
            config.demand.sectoral_residential = value
            remainder = 1.0 - value
            config.demand.sectoral_commercial = remainder / 2.0
            config.demand.sectoral_public = remainder / 2.0
        # V2b: S5/S6/S7-specific parameters
        elif parameter_name == "lng_capex":
            config.lng.capex_per_mw = value
        elif parameter_name == "lng_fuel_cost":
            config.lng.fuel_cost_per_mwh = value
        elif parameter_name == "lng_fuel_escalation":
            config.lng.fuel_escalation = value
        elif parameter_name == "lng_emission_factor":
            config.lng.emission_factor = value
        elif parameter_name == "floating_capex_premium":
            config.nearshore.floating_solar_capex_premium = value
        elif parameter_name == "floating_solar_mw":
            config.nearshore.floating_solar_mw = value
        elif parameter_name == "nearshore_solar_mw":
            config.nearshore.nearshore_solar_mw = value
        elif parameter_name == "nearshore_cable_cost":
            config.nearshore.nearshore_cable_cost_per_mw = value
        elif parameter_name == "wte_capex":
            config.wte.capex_per_kw = value
        elif parameter_name == "deployment_ramp":
            config.green_transition.deployment_ramp_mw_per_year = value
        elif parameter_name == "male_max_re":
            config.green_transition.male_max_re_share = value
        elif parameter_name == "battery_ratio":
            config.green_transition.battery_ratio = value
            config.green_transition.islanded_battery_ratio = value
        # Item-2: 6 additional high-impact parameters
        elif parameter_name == "demand_saturation":
            config.demand.demand_saturation_kwh_per_capita = value
        elif parameter_name == "male_growth_near":
            config.demand.male_growth_near_term = value
        elif parameter_name == "pv_degradation":
            config.technology.solar_pv_degradation = value
        elif parameter_name == "idc_rate":
            config.technology.idc_rate = value
            submarine_cable = config.one_grid.cable_length_km * config.technology.cable_capex_per_km
            converter_stations = config.technology.converter_station_cost_per_mw * config.one_grid.cable_capacity_mw
            landing = config.technology.landing_cost_per_end * config.technology.num_landings
            bc = submarine_cable + converter_stations + landing
            idc = bc * value
            config.one_grid.cable_capex_total = bc + idc + config.technology.grid_upgrade_cost
        elif parameter_name == "lng_capacity_mw":
            config.lng.plant_capacity_mw = value
        elif parameter_name == "subsidy_per_kwh":
            config.current_system.current_subsidy_per_kwh = value
        # P8: Transport electrification parameters
        elif parameter_name == "ev_adoption_midpoint":
            config.transport.ev_adoption_midpoint = int(value)
        elif parameter_name == "ev_motorcycle_premium":
            config.transport.e_motorcycle_premium_2026 = value
        elif parameter_name == "transport_health_damage":
            config.transport.pm25_damage_per_vkm = value
        elif parameter_name == "petrol_price":
            config.transport.petrol_price_2026 = value
        
        return config
    
    def get_parameter_summary(self) -> str:
        """
        Get a summary of all sensitivity parameters.
        """
        lines = [
            "=" * 70,
            "SENSITIVITY PARAMETERS",
            "=" * 70,
            f"{'Parameter':<25} {'Base':>12} {'Low':>12} {'High':>12} {'Unit':>10}",
            "-" * 70,
        ]
        
        for name, param in self.parameters.items():
            lines.append(
                f"{param.name:<25} {param.base_value:>12.4g} {param.low_value:>12.4g} {param.high_value:>12.4g} {param.unit:>10}"
            )
        
        return "\n".join(lines)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SENSITIVITY ANALYSIS TEST")
    print("=" * 60)
    
    config = get_config()
    analysis = SensitivityAnalysis(config)
    
    # Print parameter summary
    print(analysis.get_parameter_summary())
    
    print("\n✓ Sensitivity Analysis module loaded successfully!")
