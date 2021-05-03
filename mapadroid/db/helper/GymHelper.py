from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, case, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Gym, GymDetail, Raid
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location


class GymHelper:
    @staticmethod
    async def get(session: AsyncSession, gym_id: str) -> Optional[Gym]:
        stmt = select(Gym).where(Gym.gym_id == gym_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_locations_in_fence(session: AsyncSession, geofence_helper: GeofenceHelper) -> List[Location]:
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        stmt = select(Gym).where(and_(Gym.latitude >= min_lat,
                                      Gym.longitude >= min_lon,
                                      Gym.latitude <= max_lat,
                                      Gym.longitude <= max_lon))
        result = await session.execute(stmt)

        list_of_coords: List[Location] = []
        for gym in result:
            list_of_coords.append(Location(gym.latitude, gym.longitude))
        return geofence_helper.get_geofenced_coordinates(list_of_coords)

    @staticmethod
    async def get_gyms_in_rectangle(session: AsyncSession,
                                    ne_corner: Optional[Location] = None, sw_corner: Optional[Location] = None,
                                    old_ne_corner: Optional[Location] = None, old_sw_corner: Optional[Location] = None,
                                    timestamp: Optional[int] = None) -> Dict[int, Tuple[Gym, GymDetail, Raid]]:
        stmt = select(Gym, GymDetail, Raid) \
            .join(GymDetail, GymDetail.gym_id == Gym.gym_id, isouter=False) \
            .join(Raid, Raid.gym_id == Gym.gym_id, isouter=True)
        where_conditions = []
        if ne_corner and sw_corner:
            where_conditions.append(and_(Gym.latitude >= sw_corner.lat,
                                         Gym.longitude >= sw_corner.lng,
                                         Gym.latitude <= ne_corner.lat,
                                         Gym.longitude <= ne_corner.lng))
        if old_ne_corner and old_sw_corner:
            where_conditions.append(and_(Gym.latitude >= old_sw_corner.lat,
                                         Gym.longitude >= old_sw_corner.lng,
                                         Gym.latitude <= old_ne_corner.lat,
                                         Gym.longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(Gym.last_scanned >= datetime.utcfromtimestamp(timestamp))

        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        gyms: Dict[int, Tuple[Gym, GymDetail, Raid]] = {}
        for (gym, gym_detail, raid) in result:
            gyms[gym.gym_id] = (gym, gym_detail, raid)
        return gyms

    @staticmethod
    async def get_gym_count(session: AsyncSession) -> Dict[str, int]:
        """
        DbStatsReader::get_gym_count
        Args:
            session:

        Returns: Dict[team_as_str, count]

        """
        stmt = select(
                case((Gym.team_id == 0, "WHITE"),
                     (Gym.team_id == 1, "Blue"),
                     (Gym.team_id == 2, "Red"),
                     else_="Yellow"),
                func.count(Gym.team_id))\
            .select_from(Gym)\
            .group_by(Gym.team_id)
        result = await session.execute(stmt)
        team_count: Dict[str, int] = {}
        for team, count in result:
            team_count[team] = count
        return team_count