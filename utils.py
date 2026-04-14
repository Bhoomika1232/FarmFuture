from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def get_geotag_data(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if not exif_data:
            return None, None

        gps_info = {}
        for tag, value in exif_data.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = value[t]

        if 'GPSLatitude' in gps_info:
            # Convert DMS to Decimal Degrees
            def convert_to_degrees(value):
                d = float(value[0])
                m = float(value[1])
                s = float(value[2])
                return d + (m / 60.0) + (s / 3600.0)

            lat = convert_to_degrees(gps_info['GPSLatitude'])
            lng = convert_to_degrees(gps_info['GPSLongitude'])
            
            # Check for S or W indicators
            if gps_info['GPSLatitudeRef'] == 'S': lat = -lat
            if gps_info['GPSLongitudeRef'] == 'W': lng = -lng
            
            return lat, lng
    except Exception as e:
        print(f"Metadata error: {e}")
    return None, None