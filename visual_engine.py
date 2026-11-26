import subprocess
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import contextily as ctx
import geopandas as gpd
from shapely.geometry import LineString
from pyproj import Transformer

def _run(args):
    subprocess.run(args, check=True)

def apply_cinematic_camera(video, duration):
    video = Path(video)
    temp = video.with_name(video.stem + '_camera.mp4')
    frames = max(2, int(duration * 24))
    ease = f'(1-pow(1-min(on/{frames},1),3))'
    vf = (f"zoompan=z='1+0.075*{ease}':x='(iw-iw/zoom)*(0.5+0.025*{ease})':"
          f"y='(ih-ih/zoom)*(0.5-0.018*{ease})':d=1:s=1080x1920:fps=24,"
          'vignette=PI/5,format=yuv420p')
    _run(['ffmpeg','-y','-i',str(video),'-vf',vf,'-t',str(duration),'-an','-c:v','libx264','-preset','veryfast','-crf','21',str(temp)])
    temp.replace(video)

def render_map_scene(scene, output, duration):
    center = scene.get('map_center', [20.5937, 78.9629])
    if not isinstance(center, list) or len(center) != 2:
        raise ValueError('map_center must be [latitude, longitude]')
    lat, lon = map(float, center)
    zoom = max(3, min(12, int(scene.get('map_zoom', 5))))
    route = scene.get('route_points', [])
    outdir = Path(output).with_suffix('')
    frames_dir = outdir / 'frames'
    frames_dir.mkdir(parents=True, exist_ok=True)
    transformer = Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True)
    cx, cy = transformer.transform(lon, lat)
    span = 20037508.34 / (2 ** max(1, zoom - 1))
    route_xy = [transformer.transform(float(p[1]), float(p[0])) for p in route if isinstance(p, list) and len(p) == 2]
    borders = None
    try:
        borders = gpd.read_file("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson").to_crs("EPSG:3857")
    except Exception as border_exc:
        print("Country border overlay unavailable:", border_exc)
    frame_count = max(24, int(duration * 24))
    for frame in range(frame_count):
        progress = frame / max(1, frame_count - 1)
        eased = 1 - (1 - progress) ** 3
        fig, ax = plt.subplots(figsize=(6, 10), dpi=180)
        animated_span = span * (1.0 - 0.22 * eased)
        ax.set_xlim(cx - animated_span, cx + animated_span); ax.set_ylim(cy - animated_span, cy + animated_span)
        ax.set_facecolor('#10151f')
        try:
            ctx.add_basemap(ax, source=ctx.providers.CartoDB.DarkMatter, crs='EPSG:3857', attribution=False, zoom=zoom)
        except Exception as exc:
            print('CartoDB tile fallback:', exc)
            try:
                ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, crs='EPSG:3857', attribution=False, zoom=zoom)
            except Exception as fallback_exc:
                print('Esri imagery fallback:', fallback_exc)
        if borders is not None:
            borders.boundary.plot(ax=ax, color="#00d9ff", linewidth=5, alpha=0.16, zorder=3)
            borders.boundary.plot(ax=ax, color="#65eaff", linewidth=1.0, alpha=0.75, zorder=4)
        if len(route_xy) >= 2:
            line = LineString(route_xy); xs, ys = line.xy
            count = max(2, int(len(xs) * eased))
            ax.plot(xs[:count], ys[:count], color='#00d9ff', linewidth=9, alpha=.18)
            ax.plot(xs[:count], ys[:count], color='#62efff', linewidth=2.5, linestyle=(progress * 8.0, (5, 3)))
            ax.scatter([xs[0]], [ys[0]], s=60, c='white', edgecolors='#00d9ff', linewidths=2, zorder=5)
            if count >= len(xs): ax.scatter([xs[-1]], [ys[-1]], s=60, c='white', edgecolors='#00d9ff', linewidths=2, zorder=5)
        ax.axis('off'); fig.subplots_adjust(0, 0, 1, 1)
        fig.savefig(frames_dir / f'frame_{frame:04d}.png', facecolor='#10151f', pad_inches=0)
        plt.close(fig)
    _run(['ffmpeg','-y','-framerate','24','-i',str(frames_dir / 'frame_%04d.png'),'-vf','scale=1080:1920:flags=lanczos,vignette=PI/5,format=yuv420p','-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','21',str(output)])
