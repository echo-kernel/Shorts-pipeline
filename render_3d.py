import bpy
import math

# Clear existing objects
bpy.ops.wm.read_factory_settings(use_empty=True)

# Scene setup for vertical 9:16 Shorts
scene = bpy.context.scene
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 240  # 10 seconds

# Camera
cam_data = bpy.data.cameras.new("Camera")
cam_obj = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.location = (0, -7, 0)
cam_obj.rotation_euler = (math.radians(90), 0, 0)

# Light
light_data = bpy.data.lights.new(name="Sun", type='SUN')
light_data.energy = 4.0
light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
scene.collection.objects.link(light_obj)
light_obj.location = (5, -5, 5)

# 3D Sphere (Planet / Atom / Core)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.8, location=(0, 0, 0))
sphere = bpy.context.active_object

# Metallic / Sci-fi Material
mat = bpy.data.materials.new(name="GlowMat")
mat.use_nodes = True
nodes = mat.node_tree.nodes
principled = nodes.get("Principled BSDF")
principled.inputs["Metallic"].default_value = 0.8
principled.inputs["Roughness"].default_value = 0.2
principled.inputs["Base Color"].default_value = (0.1, 0.4, 0.9, 1.0)
sphere.data.materials.append(mat)

# Animate 360-degree rotation
sphere.rotation_euler = (0, 0, 0)
sphere.keyframe_insert(data_path="rotation_euler", frame=1)
sphere.rotation_euler = (0, 0, math.radians(360))
sphere.keyframe_insert(data_path="rotation_euler", frame=240)

# Output format
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.filepath = "./rendered_3d.mp4"

# Render animation
bpy.ops.render.render(animation=True)
