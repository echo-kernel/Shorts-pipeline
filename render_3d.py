import bpy
import math
import random
import sys

# 1. Read duration from CLI
duration = 14.0
if "--" in sys.argv:
    try:
        duration = float(sys.argv[sys.argv.index("--") + 1])
    except Exception:
        pass

fps = 24
total_frames = int(duration * fps)
cut1 = total_frames // 3
cut2 = (total_frames * 2) // 3

# 2. Reset Scene & Configure Vertical 1080x1920
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.render.fps = fps
scene.frame_start = 1
scene.frame_end = total_frames

scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderEngineEEVEENext') else 'BLENDER_EEVEE'
if hasattr(scene, 'eevee'):
    scene.eevee.taa_render_samples = 16
    if hasattr(scene.eevee, 'use_bloom'):
        scene.eevee.use_bloom = True

# Deep Space World
world = bpy.data.worlds.new("SpaceWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.005, 0.008, 0.02, 1.0)

# Materials
def make_glow(name, color, strength=5.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    m.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m

def make_metal(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = 0.95
        bsdf.inputs["Roughness"].default_value = 0.15
    return m

mat_cyan = make_glow("Cyan", (0.0, 0.85, 1.0, 1.0), 4.5)
mat_magenta = make_glow("Magenta", (1.0, 0.15, 0.65, 1.0), 5.0)
mat_gold = make_metal("Gold", (1.0, 0.75, 0.15, 1.0))
mat_dark_metal = make_metal("DarkMetal", (0.08, 0.15, 0.35, 1.0))
mat_star = make_glow("Star", (1.0, 1.0, 1.0, 1.0), 6.0)

# ==========================================
# SET 1 (Located at X=0): Quantum Core
# ==========================================
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.5, location=(0, 0, 0))
core = bpy.context.active_object
core.data.materials.append(mat_dark_metal)

bpy.ops.mesh.primitive_torus_add(major_radius=2.4, minor_radius=0.07, location=(0, 0, 0))
ring1 = bpy.context.active_object
ring1.data.materials.append(mat_gold)

bpy.ops.mesh.primitive_torus_add(major_radius=3.0, minor_radius=0.05, location=(0, 0, 0))
ring2 = bpy.context.active_object
ring2.data.materials.append(mat_cyan)

# ==========================================
# SET 2 (Located at X=50): Neon Warp Tunnel
# ==========================================
tunnel_rings = []
for i in range(18):
    y_pos = i * 2.5
    bpy.ops.mesh.primitive_torus_add(major_radius=2.6, minor_radius=0.06, location=(50, y_pos, 0))
    tr = bpy.context.active_object
    tr.rotation_euler = (math.radians(90), 0, 0)
    tr.data.materials.append(mat_cyan if i % 2 == 0 else mat_magenta)
    tunnel_rings.append(tr)

# ==========================================
# SET 3 (Located at X=100): Crystal Matrix
# ==========================================
crystals = []
for gx in range(-2, 3):
    for gy in range(-2, 3):
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.35, depth=1.6, location=(100 + gx * 1.4, gy * 1.4, 0))
        c = bpy.context.active_object
        c.data.materials.append(mat_gold if (gx + gy) % 2 == 0 else mat_cyan)
        crystals.append(c)

# Lights for Sets 1 & 3
for lx in [0, 100]:
    ld = bpy.data.lights.new(f"Light_{lx}", type='POINT')
    ld.energy = 1500.0
    ld.color = (0.2, 0.85, 1.0)
    lo = bpy.data.objects.new(f"Light_{lx}", ld)
    scene.collection.objects.link(lo)
    lo.location = (lx + 3, -4, 4)

# Camera Setup
cam_data = bpy.data.cameras.new("MainCam")
cam_data.lens = 32.0
cam_obj = bpy.data.objects.new("MainCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Helper to snap camera cleanly between cuts (CONSTANT interpolation)
def set_cam_key(frame, loc, rot_deg):
    cam_obj.location = loc
    cam_obj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    cam_obj.keyframe_insert(data_path="location", frame=frame)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=frame)

# --- SCENE 1 ANIMATION (Frames 1 to cut1-1): Quantum Core Orbit ---
set_cam_key(1, (0, -7.5, 0.5), (86, 0, 0))
set_cam_key(cut1 - 1, (3.2, -5.8, 1.8), (74, 0, 28))

core.rotation_euler = (0, 0, 0)
core.keyframe_insert(data_path="rotation_euler", frame=1)
core.rotation_euler = (math.radians(180), math.radians(360), 0)
core.keyframe_insert(data_path="rotation_euler", frame=cut1)

ring1.rotation_euler = (math.radians(45), 0, 0)
ring1.keyframe_insert(data_path="rotation_euler", frame=1)
ring1.rotation_euler = (math.radians(405), math.radians(240), 0)
ring1.keyframe_insert(data_path="rotation_euler", frame=cut1)

ring2.rotation_euler = (math.radians(-45), 0, 0)
ring2.keyframe_insert(data_path="rotation_euler", frame=1)
ring2.rotation_euler = (math.radians(-45), math.radians(-360), math.radians(180))
ring2.keyframe_insert(data_path="rotation_euler", frame=cut1)

# --- SCENE 2 ANIMATION (Frames cut1 to cut2-1): High-Speed Warp Tunnel ---
set_cam_key(cut1, (50, -1.0, 0), (90, 0, 0))
set_cam_key(cut2 - 1, (50, 32.0, 0), (90, 180, 0))

# --- SCENE 3 ANIMATION (Frames cut2 to total_frames): Crystal Matrix Sweep ---
set_cam_key(cut2, (100, -7.0, 5.5), (52, 0, 0))
set_cam_key(total_frames, (103.5, -4.5, 3.5), (58, 0, 35))

for idx, c in enumerate(crystals):
    c.rotation_euler = (0, 0, 0)
    c.keyframe_insert(data_path="rotation_euler", frame=cut2)
    c.rotation_euler = (0, 0, math.radians(360 if idx % 2 == 0 else -360))
    c.keyframe_insert(data_path="rotation_euler", frame=total_frames)

# Make transitions at cut1-1 and cut2-1 instant hard cuts (no sliding camera across empty space)
if cam_obj.animation_data and cam_obj.animation_data.action:
    for fcurve in cam_obj.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            if int(kp.co.x) in [cut1 - 1, cut2 - 1]:
                kp.interpolation = 'CONSTANT'

# Export MP4
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
scene.render.ffmpeg.ffmpeg_preset = 'REALTIME'
scene.render.filepath = "./blender_3d_render.mp4"

bpy.ops.render.render(animation=True)
