from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from time import sleep

import geopandas as gpd
import numpy as np

import ipywidgets as ipw
import ipyleaflet as ipl

# from ipywidgets import widgets, Layout, IntSlider, jslink

DEFAULT_MAP_LAYOUT = ipw.Layout(width="750px", height="750px")
DEFAULT_BASEMAP = ipl.basemaps.NASAGIBS.ViirsEarthAtNight2012
DEFAULT_CONTROL_WIDTH = ipw.Layout(width="200px")

# This is the highest to opacity seems to get for the smoke layers.
# They appear darker when layered bc of the overlap.
MAX_SMOKE_OPACITY = 0.2

DEFAULT_GEODATA_STYLE = dict(
    color="black",
    weight=1,
    fillColor="#" + "3" * 6,
    opacity=MAX_SMOKE_OPACITY,  # Make the smoke outlines semi-transparent
)


@dataclass
class MarkerInfo:
    name: str
    location: tuple
    icon_url: str
    icon_size: tuple = None

    def marker(self):
        """
        Create a marker with an icon.
        """

        icon = ipl.Icon(icon_url=self.icon_url, icon_size=self.icon_size)
        marker = ipl.Marker(
            location=self.location, draggable=False, icon=icon, name=self.name
        )
        return marker


MOORHEAD = MarkerInfo(
    name="Moorhead, MN",
    location=(46.873889, -96.767222),
    icon_url=(
        "https://thenounproject.com/api/private/icons/1336/edit/?"
        "backgroundShape=SQUARE&backgroundShapeColor=%23000000&"
        "backgroundShapeOpacity=0&"
        "exportSize=752&flipX=false&flipY=false&"
        "foregroundColor=%23FFd65B&foregroundOpacity=1&"
        "imageFormat=png&rotation=0"
    ),
)

MSUM_SMOKE = MarkerInfo(
    name="Moorhead, MN",
    location=(46.873889, -96.767222),
    icon_url=("https://physics.mnstate.edu/craig/MSUMtr.png"),
)

MSUM_CLEAR = MarkerInfo(
    name="Moorhead, MN",
    location=(46.873889, -96.767222),
    icon_url=("https://physics.mnstate.edu/craig/MSUMt.png"),
)

TRNP = MarkerInfo(
    name="Theodore Roosevelt National Park",
    location=(47.177778, -103.430556),
    icon_url=(
        "https://thenounproject.com/api/private/icons/5844572/edit/?"
        "backgroundShape=SQUARE&backgroundShapeColor=%23000000&"
        "backgroundShapeOpacity=0&"
        "exportSize=752&flipX=false&flipY=false&"
        "foregroundColor=%238B4513&foregroundOpacity=1&"
        "imageFormat=png&rotation=0"
    ),
    icon_size=(60, 60),
)


@dataclass
class ShapeFiles:
    shapes_path: Path

    def __post_init__(self):
        shapes = self.shapes_path.glob("**/*.shp")
        self.shape_dict = {f.stem: str(f) for f in shapes}

    @property
    def names(self):
        return sorted(self.shape_dict.keys())

    def __getitem__(self, key):
        """
        Add a dict-like interface to the shapefiles.
        """
        return self.shape_dict[key]

    def date(self, shape):
        """
        Extract the date from the shapefile name.

        Parameters
        ----------
        shape: str
            The name of the shapefile.

        Returns
        -------
        date: `datetime.date`
            The date of the shapefile.
        """
        return date(
            year=int(shape[9:13]), month=int(shape[13:15]), day=int(shape[15:17])
        )

    def geo_data(self, shape, style=None):
        """
        Create a GeoData object from the shapefile.

        Parameters
        ----------
        shape: str
            The name of the shapefile.

        style: dict, optional
            The style of the GeoData object. Default is DEFAULT_GEODATA_STYLE.

        Returns
        -------
        geo_data: `ipyleaflet.GeoData`
            The GeoData object.
        """
        return ipl.GeoData(
            geo_dataframe=gpd.read_file(self[shape]),
            style=style if style is not None else DEFAULT_GEODATA_STYLE,
            name=shape,
        )


def construct_map(map_layout=None, basemap=None):
    """
    Construct a map with a default layout and basemap

    Parameters
    ----------

    map_layout: `ipywidgets.Layout`, optional
        The layout for the map.

    basemap: `ipyleaflet.basemaps`, optional
        The basemap for the map.

    Returns
    -------
    map: `ipyleaflet.Map`
        The map object.
    """
    if map_layout is None:
        map_layout = DEFAULT_MAP_LAYOUT

    if basemap is None:
        basemap = DEFAULT_BASEMAP

    map = ipl.Map(center=(40, -96), zoom=4, layout=map_layout, basemap=basemap)

    map.add(ipl.FullScreenControl(position="topright"))

    return map


@dataclass
class SmokeMap:
    map: ipl.Map
    moorhead: ipl.Marker = None
    trnp: ipl.Marker = None
    date_display: ipw.HTML = None
    current_smoke: ipl.GeoData = None
    next_smoke: ipl.GeoData = None
    shapes: ShapeFiles = None
    date_selection: ipw.SelectionSlider = None
    _smoke_layers: list[ipl.GeoData] = field(default_factory=list)

    def __post_init__(self):
        self.date_display = ipw.HTML()
        self._set_date_display_value()
        # Chose this location by mousing around near the top of the map.
        # There is no default location like "topcenter."
        # Ha ha ha, controls don't have a location.
        # location = (59.5343, -96.8272)
        self.map.add(ipl.WidgetControl(widget=self.date_display, position="bottomleft"))

    def _set_date_display_value(self, shape=None):
        if shape is None:
            value = ""
        else:
            value = self.shapes.date(shape).strftime("%Y-%m-%d")
        self.date_display.value = f"<h1>Date: {value}</h1>"

    def _set_smoke_opacity(self, smoke, opacity):
        """
        Set the opacity of a smoke layer.

        Parameters
        ----------
        smoke: `ipyleaflet.GeoData`
            The smoke layer.

        opacity: float
            The opacity of the smoke layer.
        """
        # Need to force a copy of the current style dict so that when we
        # update the opacity the map knows that something has change. The
        # change is triggered by a change in the id of the style dict, not
        # by changes in the dict contents.
        style = dict(smoke.style)
        style["opacity"] = opacity
        style["fillOpacity"] = opacity
        smoke.style = style

    def set_current_smoke(self, shape, opacity=MAX_SMOKE_OPACITY):
        """
        Set the current smoke layer.

        Parameters
        ----------
        shape: str
            The name of the shapefile.

        opacity: float, optional
            The opacity of the smoke layer. Default is MAX_SMOKE_OPACITY.
        """
        old_smoke = self.current_smoke
        self.current_smoke = self.shapes.geo_data(shape)
        self._set_smoke_opacity(self.current_smoke, opacity)
        self.current_smoke.opacity = opacity
        self.map.add(self.current_smoke)
        self._smoke_layers.append(self.current_smoke)
        self._set_date_display_value(shape)
        if old_smoke is not None:
            self.map.remove(old_smoke)
            self._smoke_layers.remove(old_smoke)

    def set_next_smoke(self, shape, opacity=0):
        """
        Set the next smoke layer.

        Parameters
        ----------
        shape: str
            The name of the shapefile.

        opacity: float, optional
            The opacity of the smoke layer. Default is 0.
        """
        self.next_smoke = self.shapes.geo_data(shape)
        self._set_smoke_opacity(self.next_smoke, opacity)
        self.next_smoke.opacity = opacity
        self.map.add(self.next_smoke)
        self._smoke_layers.append(self.next_smoke)

    def cross_fade(self, fade_duration=0.2, max_opacity=MAX_SMOKE_OPACITY, steps=10):
        """
        Cross fade the current and next smoke layers.

        Parameters
        ----------
        fade_duration: float, optional
            The duration of the fade in seconds.

        max_opacity: float, optional
            The maximum opacity of the smoke layers.

        steps: int, optional
            The number of steps in the fade.
        """
        if self.current_smoke is None or self.next_smoke is None:
            raise ValueError(
                "Must set current and next smoke layers " "before cross fading."
            )

        self._set_date_display_value(self.current_smoke.name)

        for opacity in np.linspace(max_opacity, 0, num=steps):
            self._set_smoke_opacity(self.current_smoke, opacity)
            self._set_smoke_opacity(self.next_smoke, max_opacity - opacity)
            sleep(fade_duration / steps)

        self._set_date_display_value(self.next_smoke.name)

    def animate(
        self,
        fade_duration=0.2,
        fade_steps=10,
        max_n_smoke=None,
        max_smoke_opacity=MAX_SMOKE_OPACITY,
    ):
        """
        Animate the smoke layers.

        Parameters
        ----------
        fade_duration: float, optional
            The duration of the fade in seconds.

        fade_steps: int, optional
            The number of steps in the fade.

        max_n_smoke: int, optional
            The maximum number of smoke layers to animate.
            Default is None, which animates all smoke layers.

        max_smoke_opacity: float, optional
            The maximum opacity of the smoke layers.
        """
        if max_n_smoke is None:
            max_n_smoke = len(self.shapes.names)

        self.set_current_smoke(self.shapes.names[0], opacity=max_smoke_opacity)

        for shape in self.shapes.names[1:max_n_smoke]:
            self.set_next_smoke(shape)
            self.cross_fade(
                fade_duration=fade_duration,
                steps=fade_steps,
                max_opacity=max_smoke_opacity,
            )
            self.map.remove(self.current_smoke)
            self._smoke_layers.remove(self.current_smoke)
            self.current_smoke = self.next_smoke

    def clear_smoke(self):
        """
        Clear the smoke layers.
        """
        for smoke in self._smoke_layers:
            self.map.remove(smoke)
        self._smoke_layers = []

    def _date_select_observer(self, change):
        """
        The observer for the date selection widget.
        """
        self.set_current_smoke(self.shapes.names[change["new"]])

    def date_select_on(self):
        """
        Turn on the date selection widget.
        """
        if self.date_selection is None:
            self.date_selection = ipw.Dropdown(
                options=range(len(self.shapes.names)),
                value=0,
                description="Date:",
                disabled=False,
                continuous_update=False,
                orientation="horizontal",
                readout=True,
                layout=DEFAULT_CONTROL_WIDTH,
            )
            self._date_selection_control = ipl.WidgetControl(
                widget=self.date_selection, position="bottomleft"
            )
            self.map.add(self._date_selection_control)
            self.date_selection.observe(self._date_select_observer, names="value")
            # self.date_selection.observe(self.date_select, names='value')

    def date_select_off(self):
        """
        Turn off the date selection widget.
        """
        if self.date_selection is not None:
            self.map.remove(self._date_selection_control)
            self.date_selection = None
