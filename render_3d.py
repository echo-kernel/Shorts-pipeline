import bpy
import math
import random
import os
import sys

# 1. Read duration from CLI (defaults to 50s)
duration = 50.0
if "--" in sys.argv:
    try:
        duration = float(sys.argv[sys.argv.index("--") + 1])
    except Exception:
        pass

fps = 24
total_frames = int(duration * fps)

# Divide timeline into 6 fast-paced cuts (~8-9 seconds each)
c1 = total_frames // 6
c2 = (total_frames * 2) // 6
c3 = (total_frames * 3) // 6
c4 = (total_frames * 4) // 6
c5 = (total_frames * 5) // 6

# 2. Reset Scene & Configure Vertical 1080x1920
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.render.fps = fps
scene.frame_start = 1
scene.frame_end = total_frames

# Optimize Eevee samples so 1,200+ frames render quickly on CPU
scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderEngineEEVEENext') else 'BLENDER_EEVEE'
if hasattr(scene, 'eevee'):
    scene.eevee.taa_render_samples = 8

# Deep Cosmic World
world = bpy.data.worlds.new("SpaceWorld")
scene.world = world
if hasattr(world, "use_nodes") and not world.use_nodes:
    world.use_nodes = True
if world.node_tree:
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.004, 0.006, 0.018, 1.0)

# Materials
def make_glow(name, color, strength=6.0):
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    m.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m

def make_metal(name, color, roughness=0.12):
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = 0.96
        bsdf.inputs["Roughness"].default_value = roughness
    return m

mat_cyan = make_glow("Cyan", (0.0, 0.9, 1.0, 1.0), 5.5)
mat_magenta = make_glow("Magenta", (1.0, 0.12, 0.65, 1.0), 6.0)
mat_gold = make_metal("Gold", (1.0, 0.78, 0.12, 1.0))
mat_dark_metal = make_metal("DarkMetal", (0.06, 0.12, 0.30, 1.0))
mat_star = make_glow("Star", (0.95, 0.98, 1.0, 1.0), 7.0)

# ==========================================
# SET 1 (X=0): Quantum Core + Energy Cage
# ==========================================
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.45, location=(0, 0, 0))
core = bpy.context.active_object
core.data.materials.append(mat_dark_metal)

bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.62, location=(0, 0, 0))
cage = bpy.context.active_object
w_mod = cage.modifiers.new(name="Wire", type='WIREFRAME')
w_mod.thickness = 0.025
cage.data.materials.append(mat_cyan)

bpy.ops.mesh.primitive_torus_add(major_radius=2.35, minor_radius=0.07, location=(0, 0, 0))
ring1 = bpy.context.active_object
ring1.data.materials.append(mat_gold)

bpy.ops.mesh.primitive_torus_add(major_radius=2.95, minor_radius=0.05, location=(0, 0, 0))
ring2 = bpy.context.active_object
ring2.data.materials.append(mat_magenta)

# ==========================================
# SET 2 (X=50): Extended Neon Warp Tunnel
# ==========================================
for i in range(36):
    y_pos = i * 2.2
    bpy.ops.mesh.primitive_torus_add(major_radius=2.5, minor_radius=0.06, location=(50, y_pos, 0))
    tr = bpy.context.active_object
    tr.rotation_euler = (math.radians(90), 0, 0)
    tr.data.materials.append(mat_cyan if i % 2 == 0 else mat_magenta)

# ==========================================
# SET 3 (X=100): Pulsing Crystal Matrix
# ==========================================
crystals = []
for gx in range(-2, 3):
    for gy in range(-2, 3):
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.36, depth=1.8, location=(100 + gx * 1.35, gy * 1.35, 0))
        c = bpy.context.active_object
        c.data.materials.append(mat_gold if (gx + gy) % 2 == 0 else mat_cyan)
        crystals.append(c)

# Procedural 3D Starfield across all 3 sets
random.seed(108)
for base_x in [0, 50, 100]:
    for _ in range(45):
        sx = base_x + random.uniform(-12, 12)
        sy = random.uniform(-10, 75)
        sz = random.uniform(-14, 14)
        if abs(sx - base_x) < 3.5 and abs(sz) < 3.5:
            continue
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.03, 0.065), location=(sx, sy, sz))
        st = bpy.context.active_object
        st.data.materials.append(mat_star)

# Cinematic Rim & Key Lighting
for lx in [0, 100]:
    ld1 = bpy.data.lights.new(f"Key_{lx}", type='POINT')
    ld1.energy = 1800.0
    ld1.color = (0.1, 0.85, 1.0)
    lo1 = bpy.data.objects.new(f"Key_{lx}", ld1)
    scene.collection.objects.link(lo1)
    lo1.location = (lx + 3.5, -4.0, 4.0)

    ld2 = bpy.data.lights.new(f"Rim_{lx}", type='POINT')
    ld2.energy = 1200.0
    ld2.color = (1.0, 0.2, 0.7)
    lo2 = bpy.data.objects.new(f"Rim_{lx}", ld2)
    scene.collection.objects.link(lo2)
    lo2.location = (lx - 3.5, 3.0, -2.5)

# Camera Setup
cam_data = bpy.data.cameras.new("MainCam")
cam_data.lens = 30.0
cam_obj = bpy.data.objects.new("MainCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

def set_cam_key(frame, loc, rot_deg, interp='BEZIER'):
    bpy.context.preferences.edit.keyframe_new_interpolation_type = interp
    cam_obj.location = loc
    cam_obj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    cam_obj.keyframe_insert(data_path="location", frame=frame)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=frame)

# --- CUT 1 (0% - 16%): Quantum Core Wide Push-In ---
set_cam_key(1, (-1.5, -8.0, 0.4), (87, 0, -10), interp='BEZIER')
set_cam_key(c1 - 1, (2.6, -5.4, 1.5), (76, 0, 25), interp='CONSTANT')

# --- CUT 2 (16% - 33%): Warp Tunnel Forward Rush ---
set_cam_key(c1, (50, -1.0, 0), (90, 0, 0), interp='BEZIER')
set_cam_key(c2 - 1, (50, 34.0, 0), (90, 180, 0), interp='CONSTANT')

# --- CUT 3 (33% - 50%): Crystal Matrix High Sweep ---
set_cam_key(c2, (100, -7.2, 5.2), (54, 0, 0), interp='BEZIER')
set_cam_key(c3 - 1, (103.5, -4.2, 3.2), (60, 0, 38), interp='CONSTANT')

# --- CUT 4 (50% - 66%): Quantum Core Dramatic Low-Angle Close-Up ---
set_cam_key(c3, (2.2, 5.0, -2.2), (112, 0, 155), interp='BEZIER')
set_cam_key(c4 - 1, (-2.5, 4.2, 1.8), (68, 0, -148), interp='CONSTANT')

# --- CUT 5 (66% - 83%): Warp Tunnel High-Speed Reverse & Roll ---
set_cam_key(c4, (50, 36.0, 0), (90, 180, 0), interp='BEZIER')
set_cam_key(c5 - 1, (50, 72.0, 0), (90, 420, 0), interp='CONSTANT')

# --- CUT 6 (83% - 100%): Crystal Matrix Tight Orbit Finale ---
set_cam_key(c5, (96.5, -4.0, 2.6), (62, 0, -40), interp='BEZIER')
set_cam_key(total_frames, (100, -6.5, 4.5), (55, 0, 0), interp='BEZIER')

# Continuous Object Animations across full duration
core.rotation_euler = (0, 0, 0)
core.keyframe_insert(data_path="rotation_euler", frame=1)
core.rotation_euler = (math.radians(540), math.radians(1080), 0)
core.keyframe_insert(data_path="rotation_euler", frame=total_frames)

cage.rotation_euler = (0, 0, 0)
cage.keyframe_insert(data_path="rotation_euler", frame=1)
cage.rotation_euler = (math.radians(-540), math.radians(-810), math.radians(270))
cage.keyframe_insert(data_path="rotation_euler", frame=total_frames)

ring1.rotation_euler = (math.radians(45), 0, 0)
ring1.keyframe_insert(data_path="rotation_euler", frame=1)
ring1.rotation_euler = (math.radians(1125), math.radians(720), 0)
ring1.keyframe_insert(data_path="rotation_euler", frame=total_frames)

ring2.rotation_euler = (math.radians(-45), 0, 0)
ring2.keyframe_insert(data_path="rotation_euler", frame=1)
ring2.rotation_euler = (math.radians(-45), math.radians(-1080), math.radians(540))
ring2.keyframe_insert(data_path="rotation_euler", frame=total_frames)

for idx, c in enumerate(crystals):
    c.rotation_euler = (0, 0, 0)
    c.keyframe_insert(data_path="rotation_euler", frame=1)
    c.rotation_euler = (0, 0, math.radians(1080 if idx % 2 == 0 else -1080))
    c.keyframe_insert(data_path="rotation_euler", frame=total_frames)

    base_z = 0.45 if idx % 2 == 0 else -0.45
    c.location.z = base_z
    c.keyframe_insert(data_path="location", frame=c2)
    c.location.z = -base_z
    c.keyframe_insert(data_path="location", frame=c3)
    c.location.z = base_z
    c.keyframe_insert(data_path="location", frame=c5)
    c.location.z = -base_z
    c.keyframe_insert(data_path="location", frame=total_frames)

# Export JPEG frame sequence
os.makedirs("frames", exist_ok=True)
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 92
scene.render.filepath = "./frames/frame_"

print(f"Rendering {total_frames} frames ({duration}s) of 3D animation...")
bpy.ops.render.render(animation=True)
print("Blender render complete.")
