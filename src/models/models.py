from typing import Optional

import flask_sqlalchemy
from sqlalchemy import Integer, Text, Float
from sqlalchemy import select as sa_select
from sqlalchemy.orm import Mapped, mapped_column, column_property


db = flask_sqlalchemy.SQLAlchemy()


class SolarSystemName(db.Model):
    __tablename__ = "SolarSystemName"

    parentTypeId: Mapped[int] = mapped_column(Integer, primary_key=True)
    parentTypeId2: Mapped[int] = mapped_column(Integer, primary_key=True)
    parentTypeCategory: Mapped[str] = mapped_column(Text, primary_key=True)
    en: Mapped[Optional[str]] = mapped_column(Text)


class MapSolarSystem(db.Model):
    __tablename__ = "mapSolarSystem"

    solarSystemID: Mapped[int] = mapped_column(Integer, primary_key=True)
    regionID: Mapped[Optional[int]] = mapped_column(Integer)
    constellationID: Mapped[Optional[int]] = mapped_column(Integer)
    security: Mapped[Optional[float]] = mapped_column("securityStatus", Float)
    wormholeClassID: Mapped[Optional[int]] = mapped_column(Integer)
    x: Mapped[Optional[str]] = mapped_column(Text)
    y: Mapped[Optional[str]] = mapped_column(Text)
    z: Mapped[Optional[str]] = mapped_column(Text)
    x2D: Mapped[Optional[str]] = mapped_column(Text)
    y2D: Mapped[Optional[str]] = mapped_column(Text)


MapSolarSystem.solarSystemName = column_property(
    sa_select(SolarSystemName.en)
    .where(SolarSystemName.parentTypeId == MapSolarSystem.solarSystemID)
    .where(SolarSystemName.parentTypeCategory == "")
    .correlate(MapSolarSystem)
    .scalar_subquery()
)


class MapPlanet(db.Model):
    __tablename__ = "mapPlanet"

    planetID: Mapped[int] = mapped_column(Integer, primary_key=True)
    solarSystemID: Mapped[Optional[int]] = mapped_column(Integer)
    celestialIndex: Mapped[Optional[int]] = mapped_column(Integer)
    x: Mapped[Optional[int]] = mapped_column(Integer)
    y: Mapped[Optional[int]] = mapped_column(Integer)
    z: Mapped[Optional[int]] = mapped_column(Integer)


class MapMoon(db.Model):
    __tablename__ = "mapMoon"

    moonID: Mapped[int] = mapped_column(Integer, primary_key=True)
    solarSystemID: Mapped[Optional[int]] = mapped_column(Integer)
    celestialIndex: Mapped[Optional[int]] = mapped_column(Integer)
    orbitIndex: Mapped[Optional[int]] = mapped_column(Integer)
    x: Mapped[Optional[int]] = mapped_column(Integer)
    y: Mapped[Optional[int]] = mapped_column(Integer)
    z: Mapped[Optional[int]] = mapped_column(Integer)


class MapAsteroidBelt(db.Model):
    __tablename__ = "mapAsteroidBelt"

    asteroidBeltID: Mapped[int] = mapped_column(Integer, primary_key=True)
    solarSystemID: Mapped[Optional[int]] = mapped_column(Integer)
    positionX: Mapped[Optional[str]] = mapped_column(Text)
    positionY: Mapped[Optional[str]] = mapped_column(Text)
    positionZ: Mapped[Optional[str]] = mapped_column(Text)


class MapStargate(db.Model):
    __tablename__ = "mapStargate"

    stargateID: Mapped[int] = mapped_column(Integer, primary_key=True)
    solarSystemID: Mapped[Optional[int]] = mapped_column(Integer)
    x: Mapped[Optional[str]] = mapped_column(Text)
    y: Mapped[Optional[str]] = mapped_column(Text)
    z: Mapped[Optional[str]] = mapped_column(Text)


class EveTypeName(db.Model):
    __tablename__ = "EveTypeName"

    parentTypeId: Mapped[int] = mapped_column(Integer, primary_key=True)
    parentTypeId2: Mapped[int] = mapped_column(Integer, primary_key=True)
    parentTypeCategory: Mapped[str] = mapped_column(Text, primary_key=True)
    en: Mapped[Optional[str]] = mapped_column(Text)


class EveType(db.Model):
    __tablename__ = "EveType"

    typeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    groupID: Mapped[Optional[int]] = mapped_column(Integer)
    published: Mapped[Optional[int]] = mapped_column(Integer)


EveType.typeName = column_property(
    sa_select(EveTypeName.en)
    .where(EveTypeName.parentTypeId == EveType.typeID)
    .where(EveTypeName.parentTypeCategory == "")
    .correlate(EveType)
    .scalar_subquery()
)


class EveGroup(db.Model):
    __tablename__ = "EveGroup"

    groupID: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoryID: Mapped[Optional[int]] = mapped_column(Integer)
