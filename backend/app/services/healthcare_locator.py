"""
Healthcare Locator Service - OpenStreetMap/Overpass API + Local Data
Find hospitals and clinics using both local database and free APIs
No API key needed!

Features:
- Hybrid search (local database + OpenStreetMap)
- Distance calculation using Haversine formula
- Sorting by distance/rating
- Telemedicine services integration
- Emergency contacts
"""

import requests
import logging
import json
import os
from typing import List, Dict, Optional, Literal
from math import radians, sin, cos, sqrt, atan2
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Location:
    """Geographic location"""
    latitude: float
    longitude: float
    
    def __str__(self):
        return f"({self.latitude}, {self.longitude})"


@dataclass
class HealthcareFacility:
    """Healthcare facility data model"""
    id: str
    name: str
    facility_type: str  # hospital, clinic, doctors
    latitude: float
    longitude: float
    distance_km: float
    address: str = "Address not available"
    phone: str = "Phone not available"
    website: str = ""
    opening_hours: str = "Hours not available"
    emergency: bool = False
    rating: float = 0.0
    specialties: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON response"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.facility_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_km": self.distance_km,
            "address": self.address,
            "phone": self.phone,
            "website": self.website,
            "opening_hours": self.opening_hours,
            "emergency": self.emergency,
            "rating": self.rating,
            "specialties": self.specialties
        }


@dataclass
class TelemedicineService:
    """Telemedicine service data model"""
    id: str
    name: str
    website: str
    description: str = ""
    available_24_7: bool = True
    price_range: str = "Varies"
    rating: float = 0.0
    specialties: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON response"""
        return {
            "id": self.id,
            "name": self.name,
            "website": self.website,
            "description": self.description,
            "available_24_7": self.available_24_7,
            "price_range": self.price_range,
            "rating": self.rating,
            "specialties": self.specialties
        }


@dataclass
class EmergencyContact:
    """Emergency contact data model"""
    country: str
    country_code: str
    emergency_number: str
    name: str
    description: str
    available_24_7: bool = True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON response"""
        return {
            "country": self.country,
            "country_code": self.country_code,
            "emergency_number": self.emergency_number,
            "name": self.name,
            "description": self.description,
            "available_24_7": self.available_24_7
        }


# ============================================================================
# HEALTHCARE LOCATOR SERVICE
# ============================================================================

class HealthcareLocator:
    """
    Find nearby hospitals and clinics using local data + OpenStreetMap
    Hybrid approach: Local data first (fast), then Overpass API (comprehensive)
    
    Usage:
        locator = HealthcareLocator()
        hospitals = await locator.find_hospitals(lat, lon, radius=5)
    """
    
    def __init__(self):
        """Initialize the healthcare locator"""
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        self.nominatim_url = "https://nominatim.openstreetmap.org"
        self._telemedicine_services = None
        self._emergency_contacts = None
    
    # ========================================================================
    # MAIN SEARCH METHODS
    # ========================================================================
    
    async def find_hospitals(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
        limit: int = 10,
        sort_by: Literal["distance", "rating"] = "distance",
        emergency_only: bool = False
    ) -> List[HealthcareFacility]:
        """
        Find hospitals near a location
        
        Strategy:
        1. First try local hospitals database (fast, reliable)
        2. If no local results, try Overpass API (slower, more comprehensive)
        
        Args:
            latitude: User's latitude
            longitude: User's longitude
            radius_km: Search radius in kilometers (default 5km)
            limit: Maximum number of results (default 10)
            sort_by: Sort by "distance" or "rating"
            emergency_only: Only return hospitals with emergency services
        
        Returns:
            List of HealthcareFacility objects
        
        Example:
            hospitals = await locator.find_hospitals(19.0760, 72.8777, radius=10)
        """
        
        try:
            logger.info(f"🏥 Searching hospitals near ({latitude}, {longitude})")
            
            # STRATEGY 1: Try local database first
            hospitals = await self._find_hospitals_from_local(
                latitude, longitude, radius_km, limit, emergency_only
            )
            
            if hospitals:
                logger.info(f"✅ [LOCAL] Found {len(hospitals)} hospitals")
                return self._sort_facilities(hospitals, sort_by)
            
            # STRATEGY 2: Try Overpass API
            logger.info(f"🔍 [OVERPASS] Searching OpenStreetMap...")
            hospitals = await self._find_hospitals_from_overpass(
                latitude, longitude, radius_km, limit, emergency_only
            )
            
            if hospitals:
                logger.info(f"✅ [OVERPASS] Found {len(hospitals)} hospitals")
                return self._sort_facilities(hospitals, sort_by)
            
            logger.warning(f"⚠️ No hospitals found in {radius_km}km radius")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error finding hospitals: {str(e)}")
            return []
    
    
    async def find_clinics(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
        limit: int = 10,
        sort_by: Literal["distance", "rating"] = "distance"
    ) -> List[HealthcareFacility]:
        """
        Find clinics near a location
        
        Args:
            latitude: User's latitude
            longitude: User's longitude
            radius_km: Search radius in kilometers
            limit: Maximum results
            sort_by: Sort by "distance" or "rating"
        
        Returns:
            List of HealthcareFacility objects
        """
        
        try:
            logger.info(f"🏥 Searching clinics near ({latitude}, {longitude})")
            
            # Search using Overpass API with clinic-specific query
            clinics = await self._find_clinics_from_overpass(
                latitude, longitude, radius_km, limit
            )
            
            if clinics:
                logger.info(f"✅ Found {len(clinics)} clinics")
                return self._sort_facilities(clinics, sort_by)
            
            logger.warning(f"⚠️ No clinics found in {radius_km}km radius")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error finding clinics: {str(e)}")
            return []
    
    
    async def find_all_facilities(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
        limit: int = 10,
        sort_by: Literal["distance", "rating"] = "distance"
    ) -> Dict[str, List[HealthcareFacility]]:
        """
        Find all healthcare facilities (hospitals + clinics)
        
        Args:
            latitude: User's latitude
            longitude: User's longitude
            radius_km: Search radius in kilometers
            limit: Maximum results per type
            sort_by: Sort by "distance" or "rating"
        
        Returns:
            Dictionary with "hospitals" and "clinics" lists
        """
        
        hospitals = await self.find_hospitals(
            latitude, longitude, radius_km, limit, sort_by
        )
        clinics = await self.find_clinics(
            latitude, longitude, radius_km, limit, sort_by
        )
        
        return {
            "hospitals": hospitals,
            "clinics": clinics,
            "total_hospitals": len(hospitals),
            "total_clinics": len(clinics)
        }
    
    
    # ========================================================================
    # LOCAL DATABASE SEARCH
    # ========================================================================
    
    async def _find_hospitals_from_local(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        limit: int,
        emergency_only: bool
    ) -> List[HealthcareFacility]:
        """
        Search hospitals from local JSON file (fast & reliable)
        """
        
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(current_dir))
            hospitals_file = os.path.join(backend_dir, "data", "hospitals_india.json")
            
            if not os.path.exists(hospitals_file):
                logger.warning(f"⚠️ Local hospitals file not found")
                return []
            
            with open(hospitals_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            hospitals = []
            
            for hospital in data.get("hospitals", []):
                distance = self._calculate_distance(
                    latitude, longitude,
                    hospital.get("latitude", 0),
                    hospital.get("longitude", 0)
                )
                
                if distance <= radius_km:
                    if emergency_only and not hospital.get("emergency"):
                        continue
                    
                    facility = HealthcareFacility(
                        id=hospital.get("id", f"local_{len(hospitals)}"),
                        name=hospital.get("name", "Unknown Hospital"),
                        facility_type=hospital.get("type", "hospital"),
                        latitude=hospital.get("latitude", 0),
                        longitude=hospital.get("longitude", 0),
                        distance_km=round(distance, 2),
                        address=hospital.get("address", "Address not available"),
                        phone=hospital.get("phone", "Phone not available"),
                        website=hospital.get("website", ""),
                        opening_hours=hospital.get("opening_hours", "Hours not available"),
                        emergency=hospital.get("emergency", False),
                        rating=hospital.get("rating", 0.0),
                        specialties=hospital.get("specialties", [])
                    )
                    hospitals.append(facility)
            
            hospitals.sort(key=lambda x: x.distance_km)
            return hospitals[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error reading local hospitals: {str(e)}")
            return []
    
    
    # ========================================================================
    # OVERPASS API SEARCH
    # ========================================================================
    
    async def _find_hospitals_from_overpass(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        limit: int,
        emergency_only: bool
    ) -> List[HealthcareFacility]:
        """
        Search hospitals from Overpass API (OpenStreetMap)
        """
        
        try:
            radius_meters = int(radius_km * 1000)
            
            # Overpass query for hospitals
            query = f"""
            [out:json][timeout:25];
            (
              node["amenity"="hospital"](around:{radius_meters},{latitude},{longitude});
              way["amenity"="hospital"](around:{radius_meters},{latitude},{longitude});
              relation["amenity"="hospital"](around:{radius_meters},{latitude},{longitude});
            );
            out center;
            """
            
            response = requests.post(
                self.overpass_url,
                data={"data": query},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Overpass API error: {response.status_code}")
                return []
            
            data = response.json()
            hospitals = []
            
            for element in data.get("elements", []):
                facility = self._parse_osm_element(element, latitude, longitude)
                if facility and facility.facility_type == "hospital":
                    if emergency_only and not facility.emergency:
                        continue
                    hospitals.append(facility)
            
            return hospitals[:limit]
            
        except Exception as e:
            logger.error(f"❌ Overpass API error: {str(e)}")
            return []
    
    
    async def _find_clinics_from_overpass(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        limit: int
    ) -> List[HealthcareFacility]:
        """
        Search clinics from Overpass API
        """
        
        try:
            radius_meters = int(radius_km * 1000)
            
            # Overpass query for clinics
            query = f"""
            [out:json][timeout:25];
            (
              node["amenity"="clinic"](around:{radius_meters},{latitude},{longitude});
              way["amenity"="clinic"](around:{radius_meters},{latitude},{longitude});
              node["healthcare"](around:{radius_meters},{latitude},{longitude});
              node["doctor"](around:{radius_meters},{latitude},{longitude});
            );
            out center;
            """
            
            response = requests.post(
                self.overpass_url,
                data={"data": query},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Overpass API error: {response.status_code}")
                return []
            
            data = response.json()
            clinics = []
            
            for element in data.get("elements", []):
                facility = self._parse_osm_element(element, latitude, longitude)
                if facility:
                    clinics.append(facility)
            
            return clinics[:limit]
            
        except Exception as e:
            logger.error(f"❌ Overpass API error: {str(e)}")
            return []
    
    
    def _parse_osm_element(
        self,
        element: Dict,
        user_lat: float,
        user_lon: float
    ) -> Optional[HealthcareFacility]:
        """
        Parse Overpass API element into HealthcareFacility
        """
        
        try:
            tags = element.get("tags", {})
            
            # Get coordinates
            if "center" in element:
                lat = element["center"]["lat"]
                lon = element["center"]["lon"]
            elif "lat" in element and "lon" in element:
                lat = element["lat"]
                lon = element["lon"]
            else:
                return None
            
            # Get name and type
            name = tags.get("name", "Unknown Facility")
            amenity = tags.get("amenity", "hospital")
            facility_type = "clinic" if amenity == "clinic" else "hospital"
            
            # Calculate distance
            distance = self._calculate_distance(user_lat, user_lon, lat, lon)
            
            # Build facility object
            facility = HealthcareFacility(
                id=str(element.get("id", "")),
                name=name,
                facility_type=facility_type,
                latitude=lat,
                longitude=lon,
                distance_km=round(distance, 2),
                address=tags.get("addr:full", f"Near {lat}, {lon}"),
                phone=tags.get("phone", "Phone not available"),
                website=tags.get("website", ""),
                opening_hours=tags.get("opening_hours", "Hours not available"),
                emergency=tags.get("emergency", "").lower() == "yes",
                rating=0.0,  # OSM doesn't have ratings
                specialties=[]
            )
            
            return facility
            
        except Exception as e:
            logger.error(f"❌ Error parsing OSM element: {str(e)}")
            return None
    
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula
        
        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate
        
        Returns:
            Distance in kilometers
        """
        
        R = 6371  # Earth's radius in km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    
    def _sort_facilities(
        self,
        facilities: List[HealthcareFacility],
        sort_by: str
    ) -> List[HealthcareFacility]:
        """
        Sort facilities by distance or rating
        """
        
        if sort_by == "rating":
            return sorted(facilities, key=lambda x: (-x.rating, x.distance_km))
        else:  # Default: distance
            return sorted(facilities, key=lambda x: (x.distance_km, -x.rating))
    
    
    # ========================================================================
    # TELEMEDICINE SERVICES
    # ========================================================================
    
    async def get_telemedicine_services(self) -> List[TelemedicineService]:
        """
        Get list of telemedicine services
        
        Returns:
            List of TelemedicineService objects
        """
        
        if self._telemedicine_services is not None:
            return self._telemedicine_services
        
        services = [
            TelemedicineService(
                id="tele_001",
                name="Practo",
                website="https://www.practo.com",
                description="Online doctor consultation with specialists",
                available_24_7=True,
                price_range="₹200-₹1000",
                rating=4.5,
                specialties=["General Medicine", "Pediatrics", "Dermatology", "Gynecology"]
            ),
            TelemedicineService(
                id="tele_002",
                name="1mg",
                website="https://www.1mg.com",
                description="Online consultations and medicine delivery",
                available_24_7=True,
                price_range="₹150-₹800",
                rating=4.3,
                specialties=["General Medicine", "Ayurveda", "Homeopathy"]
            ),
            TelemedicineService(
                id="tele_003",
                name="Lybrate",
                website="https://www.lybrate.com",
                description="Connect with doctors online",
                available_24_7=True,
                price_range="₹300-₹1500",
                rating=4.2,
                specialties=["Cardiology", "Neurology", "Orthopedics"]
            ),
            TelemedicineService(
                id="tele_004",
                name="MFine",
                website="https://www.mfine.co",
                description="Online doctor consultations",
                available_24_7=True,
                price_range="₹250-₹1200",
                rating=4.4,
                specialties=["General Medicine", "Psychiatry", "Nutrition"]
            ),
            TelemedicineService(
                id="tele_005",
                name="DocPrime",
                website="https://www.docprime.com",
                description="Online consultations with top doctors",
                available_24_7=True,
                price_range="₹200-₹1000",
                rating=4.1,
                specialties=["General Medicine", "Dental", "ENT"]
            ),
            TelemedicineService(
                id="tele_006",
                name="Apollo 24|7",
                website="https://www.apollo247.com",
                description="24/7 online doctor consultations",
                available_24_7=True,
                price_range="₹300-₹2000",
                rating=4.6,
                specialties=["All Specialties", "Emergency Care"]
            ),
            TelemedicineService(
                id="tele_007",
                name="MediBuddy",
                website="https://www.medibuddy.in",
                description="Corporate health benefits and consultations",
                available_24_7=True,
                price_range="₹200-₹1500",
                rating=4.0,
                specialties=["General Medicine", "Mental Health"]
            ),
            TelemedicineService(
                id="tele_008",
                name="CureJoy",
                website="https://www.curejoy.com",
                description="Alternative medicine consultations",
                available_24_7=False,
                price_range="₹500-₹2000",
                rating=3.9,
                specialties=["Ayurveda", "Yoga", "Nutrition"]
            )
        ]
        
        self._telemedicine_services = services
        return services
    
    async def get_telemedicine_services_dict(self) -> List[Dict]:
        """
        Get telemedicine services as list of dictionaries
        
        Returns:
            List of dictionaries for JSON response
        """
        services = await self.get_telemedicine_services()
        return [service.to_dict() for service in services]
    
    
    # ========================================================================
    # EMERGENCY CONTACTS
    # ========================================================================
    
    async def get_emergency_contact(self, country: str = "INDIA") -> EmergencyContact:
        """
        Get emergency contact for a country
        
        Args:
            country: Country name (default: INDIA)
        
        Returns:
            EmergencyContact object
        """
        
        country = country.upper()
        
        emergency_data = {
            "INDIA": {
                "country": "India",
                "country_code": "IN",
                "emergency_number": "108",
                "name": "Emergency Response Service (ERS)",
                "description": "Ambulance, Police, and Fire emergency services"
            },
            "USA": {
                "country": "United States",
                "country_code": "US",
                "emergency_number": "911",
                "name": "Emergency Services",
                "description": "Police, Fire, and Medical emergencies"
            },
            "UK": {
                "country": "United Kingdom",
                "country_code": "UK",
                "emergency_number": "999",
                "name": "UK Emergency Services",
                "description": "Police, Fire, and Ambulance"
            },
            "CANADA": {
                "country": "Canada",
                "country_code": "CA",
                "emergency_number": "911",
                "name": "Canadian Emergency Services",
                "description": "Police, Fire, and Medical emergencies"
            },
            "AUSTRALIA": {
                "country": "Australia",
                "country_code": "AU",
                "emergency_number": "000",
                "name": "Australian Emergency Services",
                "description": "Police, Fire, and Ambulance"
            },
            "GERMANY": {
                "country": "Germany",
                "country_code": "DE",
                "emergency_number": "112",
                "name": "European Emergency Number",
                "description": "Police, Fire, and Medical emergencies"
            },
            "FRANCE": {
                "country": "France",
                "country_code": "FR",
                "emergency_number": "112",
                "name": "European Emergency Number",
                "description": "Police, Fire, and Medical emergencies"
            },
            "JAPAN": {
                "country": "Japan",
                "country_code": "JP",
                "emergency_number": "119",
                "name": "Japanese Emergency Services",
                "description": "Fire and Ambulance (Police: 110)"
            }
        }
        
        data = emergency_data.get(country, emergency_data["INDIA"])
        
        return EmergencyContact(
            country=data["country"],
            country_code=data["country_code"],
            emergency_number=data["emergency_number"],
            name=data["name"],
            description=data["description"],
            available_24_7=True
        )
    
    async def get_emergency_contact_dict(self, country: str = "INDIA") -> Dict:
        """
        Get emergency contact as dictionary
        
        Returns:
            Dictionary for JSON response
        """
        contact = await self.get_emergency_contact(country)
        return contact.to_dict()
    
    
    # ========================================================================
    # NEAREST EMERGENCY HOSPITAL
    # ========================================================================
    
    async def find_nearest_emergency_hospital(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0
    ) -> Optional[HealthcareFacility]:
        """
        Find the nearest hospital with emergency services
        
        Args:
            latitude: User's latitude
            longitude: User's longitude
            radius_km: Search radius in kilometers
        
        Returns:
            Nearest emergency hospital or None
        """
        
        hospitals = await self.find_hospitals(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=20,
            emergency_only=True
        )
        
        if hospitals:
            return hospitals[0]  # Already sorted by distance
        return None
    
    
    # ========================================================================
    # DIRECTIONS URL
    # ========================================================================
    
    def get_directions_url(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float
    ) -> str:
        """
        Get Google Maps directions URL
        
        Args:
            from_lat, from_lon: Starting point
            to_lat, to_lon: Destination
        
        Returns:
            Google Maps directions URL
        """
        return f"https://www.google.com/maps/dir/?api=1&origin={from_lat},{from_lon}&destination={to_lat},{to_lon}&travelmode=driving"
    
    def get_nominatim_url(self, lat: float, lon: float) -> str:
        """
        Get Nominatim (OpenStreetMap) location URL
        
        Args:
            lat: Latitude
            lon: Longitude
        
        Returns:
            OpenStreetMap location URL
        """
        return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}"


# ============================================================================
# CONVENIENCE FUNCTIONS (for direct imports)
# ============================================================================

_locator: Optional[HealthcareLocator] = None

def get_healthcare_locator() -> HealthcareLocator:
    """Get singleton HealthcareLocator instance"""
    global _locator
    if _locator is None:
        _locator = HealthcareLocator()
    return _locator


async def find_hospitals(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    limit: int = 10
) -> List[HealthcareFacility]:
    """Convenience function to find hospitals"""
    locator = get_healthcare_locator()
    return await locator.find_hospitals(latitude, longitude, radius_km, limit)


async def find_clinics(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    limit: int = 10
) -> List[HealthcareFacility]:
    """Convenience function to find clinics"""
    locator = get_healthcare_locator()
    return await locator.find_clinics(latitude, longitude, radius_km, limit)


async def get_telemedicine_services() -> List[Dict]:
    """Convenience function to get telemedicine services"""
    locator = get_healthcare_locator()
    return await locator.get_telemedicine_services_dict()


async def get_emergency_contact(country: str = "INDIA") -> Dict:
    """Convenience function to get emergency contact"""
    locator = get_healthcare_locator()
    return await locator.get_emergency_contact_dict(country)


# ============================================================================
# TEST THE SERVICE
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        locator = HealthcareLocator()
        
        # Test coordinates (Mumbai)
        latitude = 19.0760
        longitude = 72.8777
        
        print("=" * 70)
        print("🏥 Testing Healthcare Locator Service")
        print("=" * 70)
        print(f"\n📍 Location: ({latitude}, {longitude}) - Mumbai, India")
        print()
        
        # Test 1: Find hospitals
        print("🔍 Searching for hospitals...")
        hospitals = await locator.find_hospitals(latitude, longitude, radius=5, limit=5)
        print(f"✅ Found {len(hospitals)} hospitals:")
        for h in hospitals:
            print(f"   • {h.name} ({h.distance_km} km) - {h.address}")
        print()
        
        # Test 2: Find clinics
        print("🔍 Searching for clinics...")
        clinics = await locator.find_clinics(latitude, longitude, radius=5, limit=5)
        print(f"✅ Found {len(clinics)} clinics:")
        for c in clinics:
            print(f"   • {c.name} ({c.distance_km} km)")
        print()
        
        # Test 3: Telemedicine services
        print("🔍 Getting telemedicine services...")
        tele_services = await locator.get_telemedicine_services()
        print(f"✅ Found {len(tele_services)} telemedicine services:")
        for t in tele_services[:3]:
            print(f"   • {t['name']} - {t['website']}")
        print()
        
        # Test 4: Emergency contact
        print("🔍 Getting emergency contact for India...")
        emergency = await locator.get_emergency_contact("INDIA")
        print(f"✅ Emergency: Call {emergency['emergency_number']} - {emergency['name']}")
        print()
        
        # Test 5: Nearest emergency hospital
        print("🔍 Searching for nearest emergency hospital...")
        emergency_hospital = await locator.find_nearest_emergency_hospital(latitude, longitude)
        if emergency_hospital:
            print(f"✅ Nearest emergency: {emergency_hospital.name} ({emergency_hospital.distance_km} km)")
        else:
            print("⚠️ No emergency hospital found nearby")
        print()
        
        print("=" * 70)
        print("✅ All tests completed!")
        print("=" * 70)
    
    asyncio.run(test())