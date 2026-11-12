import bpy
import math
import random
import sys

# 1. Read target duration from CLI
duration = 12.0
if "--" in sys.argv:
    try:
        duration = float(sys.argv[sys.argv.index("--") + 1])
    except Exception:
        pass

fps = 24
total_frames = int(duration * fps)

# 2. Reset Scene & Configure Vertical 1080x1920
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.render.fps = fps
scene.frame_start = 1
scene.frame_end = total_frames

# Optimize Eevee for fast cloud CPU rendering
scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderEngineEEVEENext') else 'BLENDER_EEVEE'
if hasattr(scene, 'eevee'):
    scene.eevee.taa_render_samples = 16
    if hasattr(scene.eevee, 'use_bloom'):
        scene.eevee.use_bloom = True

# 3. Dark Deep-Space World Background
world = bpy.data.worlds.new("SpaceWorld")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.005, 0.008, 0.02, 1.0)
    bg_node.inputs[1].default_value = 1.0

# 4. Create Materials
def create_emission_mat(name, color, strength=5.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    mat.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat

def create_metallic_mat(name, color, metallic=0.9, roughness=0.2):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return mat

mat_core = create_metallic_mat("CoreMetal", (0.08, 0.15, 0.35, 1.0))
mat_wire = create_emission_mat("CyanWire", (0.0, 0.85, 1.0, 1.0), strength=4.0)
mat_ring_gold = create_metallic_mat("GoldRing", (1.0, 0.75, 0.15, 1.0))
mat_star = create_emission_mat("StarGlow", (0.9, 0.95, 1.0, 1.0), strength=6.0)
mat_sat = create_emission_mat("MagentaSat", (1.0, 0.15, 0.65, 1.0), strength=5.0)

# 5. Build Multi-Layered 3D Central Core
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.5, location=(0, 0, 0))
core = bpy.context.active_object
core.data.materials.append(mat_core)

# Outer Glowing Wireframe Cage
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.65, location=(0, 0, 0))
wire_cage = bpy.context.active_object
wire_mod = wire_cage.modifiers.new(name="Wireframe", type='WIREFRAME')
wire_mod.thickness = 0.03
wire_cage.data.materials.append(mat_wire)

# Dual Gyroscopic Rings
bpy.ops.mesh.primitive_torus_add(major_radius=2.5, minor_radius=0.06, location=(0, 0, 0))
ring1 = bpy.context.active_object
ring1.data.materials.append(mat_ring_gold)

bpy.ops.mesh.primitive_torus_add(major_radius=3.1, minor_radius=0.05, location=(0, 0, 0))
ring2 = bpy.context.active_object
ring2.data.materials.append(mat_wire)

# 6. Orbiting 3D Satellites
satellites = []
for i in range(6):
    angle = (2 * math.pi / 6) * i
    dist = 3.8
    x = math.cos(angle) * dist
    y = math.sin(angle) * dist
    z = math.sin(angle * 2) * 0.8
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=(x, y, z))
    sat = bpy.context.active_object
    sat.data.materials.append(mat_sat)
    satellites.append((sat, angle, dist))

# 7. 3D Volumetric Starfield (120 Stars)
random.seed(42)
for _ in range(120):
    sx = random.uniform(-14, 14)
    sy = random.uniform(-14, 14)
    sz = random.uniform(-18, 18)
    if math.sqrt(sx**2 + sy**2 + sz**2) < 4.5:
        continue
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.03, 0.07), location=(sx, sy, sz))
    star = bpy.context.active_object
    star.data.materials.append(mat_star)

# 8. Three-Point Cinematic Lighting
l1_data = bpy.data.lights.new("KeyLight", type='POINT')
l1_data.energy = 1200.0
l1_data.color = (0.1, 0.85, 1.0)
l1 = bpy.data.objects.new("KeyLight", l1_data)
scene.collection.objects.link(l1)
l1.location = (4, -4, 4)

l2_data = bpy.data.lights.new("FillLight", type='POINT')
l2_data.energy = 900.0
l2_data.color = (0.9, 0.2, 1.0)
l2 = bpy.data.objects.new("FillLight", l2_data)
scene.collection.objects.link(l2)
l2.location = (-4, 3, -3)

# 9. Animated Camera & Track-To Target (Dynamic Orbit + Dolly Zoom)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
target = bpy.context.active_object

cam_data = bpy.data.cameras.new("MainCam")
cam_data.lens = 35.0
cam_obj = bpy.data.objects.new("MainCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

track = cam_obj.constraints.new(type='TRACK_TO')
track.target = target
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# Keyframe Animations across entire duration
for f in [1, total_frames // 2, total_frames]:
    progress = (f - 1) / max(1, (total_frames - 1))
    
    # Camera sweeps in a cinematic 3D arc and pushes closer
    cam_angle = math.radians(-90 + progress * 110)
    cam_radius = 9.5 - (progress * 3.0)
    cam_z = -1.5 + (progress * 3.2)
    cam_obj.location = (math.cos(cam_angle) * cam_radius, math.sin(cam_angle) * cam_radius, cam_z)
    cam_obj.keyframe_insert(data_path="location", frame=f)

    # Core & Wireframe counter-rotation
    core.rotation_euler = (progress * math.radians(180), progress * math.radians(360), 0)
    core.keyframe_insert(data_path="rotation_euler", frame=f)

    wire_cage.rotation_euler = (-progress * math.radians(180), -progress * math.radians(270), progress * math.radians(90))
    wire_cage.keyframe_insert(data_path="rotation_euler", frame=f)

    # Gyroscopic Ring 3D Tumbling
    ring1.rotation_euler = (math.radians(45) + progress * math.radians(360), progress * math.radians(180), 0)
    ring1.keyframe_insert(data_path="rotation_euler", frame=f)

    ring2.rotation_euler = (math.radians(-60), math.radians(30) + progress * math.radians(360), progress * math.radians(240))
    ring2.keyframe_insert(data_path="rotation_euler", frame=f)

# Animate Orbiting Satellites frame-by-frame
for f in range(1, total_frames + 1, 6):
    progress = (f - 1) / max(1, (total_frames - 1))
    for sat, base_angle, dist in satellites:
        cur_angle = base_angle + progress * math.radians(360)
        sat.location = (
            math.cos(cur_angle) * dist,
            math.sin(cur_angle) * dist,
            math.sin(cur_angle * 2) * 1.1
        )
        sat.keyframe_insert(data_path="location", frame=f)

# 10. Export H.264 MP4
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
scene.render.ffmpeg.ffmpeg_preset = 'REALTIME'
scene.render.filepath = "./blender_3d_render.mp4"

print(f"Rendering {total_frames} frames of full 3D animation...")
bpy.ops.render.render(animation=True)
print("Full 3D animation render complete.")
  
