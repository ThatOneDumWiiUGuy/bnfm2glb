import struct
import json
import os
import glob

class GLBExporter:
    def __init__(self, filepath):
        self.filepath = filepath
        self.dir_path = os.path.dirname(filepath)
        self.file_basename = os.path.splitext(os.path.basename(filepath))[0]
        
    def parse_glb(self):
        with open(self.filepath, 'rb') as f:
            magic = f.read(4)
            if magic != b'glTF':
                print("nada, not a glb")
                return None
                
            version = struct.unpack('<I', f.read(4))[0]
            total_length = struct.unpack('<I', f.read(4))[0]
            
            json_len = struct.unpack('<I', f.read(4))[0]
            json_type = f.read(4)
            gltf_data = json.loads(f.read(json_len).decode('utf-8'))
            
            bin_len = struct.unpack('<I', f.read(4))[0]
            bin_type = f.read(4)
            bin_buffer = f.read(bin_len)
            
        return gltf_data, bin_buffer

    def convert(self):
        parsed = self.parse_glb()
        if not parsed:
            return
        gltf, bin_buffer = parsed

        polygons = []
        strings_to_write = ["Root", "Default_Material", "mat2_fallback"]
        string_offsets = {}

        for mesh_idx, mesh in enumerate(gltf.get("meshes", [])):
            poly_name = mesh.get("name", f"polygon_{mesh_idx}")
            if poly_name not in strings_to_write:
                strings_to_write.append(poly_name)
                
            for prim in mesh.get("primitives", []):
                attrs = prim.get("attributes", {})
                pos_acc_idx = attrs.get("POSITION")
                uv_acc_idx = attrs.get("TEXCOORD_0")
                indices_idx = prim.get("indices")
                
                if pos_acc_idx is None or indices_idx is None:
                    continue
                    
                pos_acc = gltf["accessors"][pos_acc_idx]
                pos_view = gltf["bufferViews"][pos_acc["bufferView"]]
                pos_offset = pos_view.get("byteOffset", 0) + pos_acc.get("byteOffset", 0)
                pos_count = pos_acc["count"]
                
                verts = []
                for i in range(pos_count):
                    off = pos_offset + (i * 12)
                    vx, vy, vz = struct.unpack('<fff', bin_buffer[off:off+12])
                    verts.append([vx, vy, vz])
                    
                uvs = []
                if uv_acc_idx is not None:
                    uv_acc = gltf["accessors"][uv_acc_idx]
                    uv_view = gltf["bufferViews"][uv_acc["bufferView"]]
                    uv_offset = uv_view.get("byteOffset", 0) + uv_acc.get("byteOffset", 0)
                    for i in range(pos_count):
                        off = uv_offset + (i * 8)
                        tu, tv = struct.unpack('<ff', bin_buffer[off:off+8])
                        uvs.append([tu, 1.0 - tv])
                else:
                    uvs = [[0.0, 0.0] for _ in range(pos_count)]

                ind_acc = gltf["accessors"][indices_idx]
                ind_view = gltf["bufferViews"][ind_acc["bufferView"]]
                ind_offset = ind_view.get("byteOffset", 0) + ind_acc.get("byteOffset", 0)
                ind_count = ind_acc["count"]
                
                faces = []
                for i in range(0, ind_count, 3):
                    off = ind_offset + (i * 2)
                    fa, fb, fc = struct.unpack('<HHH', bin_buffer[off:off+6])
                    faces.append([fa, fb, fc])

                polygons.append({
                    "name": poly_name,
                    "vertices": verts,
                    "uvs": uvs,
                    "faces": faces
                })

        bnfm = bytearray(0x100) 

        def align_buffer(buf, alignment=16):
            while len(buf) % alignment != 0:
                buf.append(0)

        bone_chart_start = len(bnfm)
        bone_chart_count = 1
        bnfm.extend(struct.pack('>I', 0)) 
        align_buffer(bnfm)

        string_start = len(bnfm)
        for s in strings_to_write:
            string_offsets[s] = len(bnfm)
            bnfm.extend(s.encode('utf-8'))
            bnfm.append(0)
        align_buffer(bnfm)

        bone_start = len(bnfm)
        bone_count = 1
        bnfm.extend(struct.pack('>I', string_offsets["Root"]))
        bnfm.extend(struct.pack('>I', 0))                     
        bnfm.extend(struct.pack('>I', string_offsets["Root"]))
        bnfm.extend(bytes(0x18))                            
        bnfm.extend(struct.pack('>fff', 0.0, 0.0, 0.0))        
        bnfm.extend(struct.pack('>fff', 1.0, 1.0, 1.0))        
        bnfm.extend(bytes(0x14))                            
        for _ in range(32):                                    
            bnfm.extend(struct.pack('>f', 0.0))
        bnfm.extend(bytes(0x0C))                            
        align_buffer(bnfm)

        material_start = len(bnfm)
        mat_count = len(polygons)
        for _ in range(mat_count):
            bnfm.extend(struct.pack('>I', string_offsets["Default_Material"]))
            bnfm.extend(bytes(0x110))
            bnfm.extend(struct.pack('>I', string_offsets["mat2_fallback"]))
            bnfm.extend(bytes(0x110))
        align_buffer(bnfm)

        material_2_start = len(bnfm)
        for _ in range(mat_count):
            bnfm.extend(struct.pack('>I', string_offsets["Default_Material"]))
            bnfm.extend(bytes(0x38))
        align_buffer(bnfm)

        face_start = len(bnfm)
        poly_face_offsets = []
        running_face_bytes = 0
        for poly in polygons:
            poly_face_offsets.append(running_face_bytes)
            for face in poly["faces"]:
                bnfm.extend(struct.pack('>HHH', *face))
            running_face_bytes = (len(bnfm) - face_start)
        face_total_bytes = len(bnfm) - face_start
        align_buffer(bnfm)

        vert_start = len(bnfm)
        for poly in polygons:
            for idx, vert in enumerate(poly["vertices"]):
                bnfm.extend(struct.pack('>fff', *vert))  
                bnfm.extend(struct.pack('>f', 1.0))      
                bnfm.extend(struct.pack('4B', 255, 255, 255, 255)) 
                
                uv = poly["uvs"][idx]
                bnfm.extend(struct.pack('>ee', uv[0], uv[1])) 
                bnfm.extend(struct.pack('>ee', 0.0, 0.0))     
                
                bnfm.extend(struct.pack('4B', 0, 0, 0, 0))         
                bnfm.extend(struct.pack('4B', 255, 0, 0, 0))       
                bnfm.extend(struct.pack('>II', 0, 0))              
        vert_total_bytes = len(bnfm) - vert_start
        align_buffer(bnfm)

        poly_info_start = len(bnfm)
        for idx, poly in enumerate(polygons):
            bnfm.extend(struct.pack('>I', string_offsets.get(poly["name"], string_start))) 
            bnfm.extend(struct.pack('>I', 0))                                              
            bnfm.extend(struct.pack('>I', bone_chart_start))                                
            bnfm.extend(struct.pack('>I', poly_face_offsets[idx]))                         
            bnfm.extend(struct.pack('>II', 0, 0))                                          
            bnfm.extend(struct.pack('>I', len(poly["faces"]) * 3))                         
            bnfm.extend(struct.pack('>I', len(poly["vertices"])))                          
            bnfm.extend(struct.pack('>I', 1))                                              
            bnfm.extend(struct.pack('>I', idx + 1))                                        
            bnfm.extend(struct.pack('>II', 0, 0))                                          
        align_buffer(bnfm)

        struct.pack_into('>I', bnfm, 0x00, 0x57550000)       
        struct.pack_into('>I', bnfm, 0x04, string_start)      
        struct.pack_into('>I', bnfm, 0x0C, face_start)
        struct.pack_into('>I', bnfm, 0x10, face_total_bytes)
        struct.pack_into('>I', bnfm, 0x14, vert_total_bytes)
        struct.pack_into('>I', bnfm, 0x18, bone_chart_start)
        struct.pack_into('>I', bnfm, 0x20, vert_start)
        struct.pack_into('>I', bnfm, 0x24, face_start)        
        
        struct.pack_into('>I', bnfm, 0x28, 0)
        
        struct.pack_into('>I', bnfm, 0x2C, len(polygons))     
        struct.pack_into('>I', bnfm, 0x30, bone_count)        
        struct.pack_into('>I', bnfm, 0x34, len(polygons))     
        struct.pack_into('>I', bnfm, 0x38, mat_count * 6)     
        struct.pack_into('>I', bnfm, 0x3C, len(polygons))     
        struct.pack_into('>I', bnfm, 0x40, len(polygons))     
        
        struct.pack_into('>I', bnfm, 0x44, bone_chart_count)  
        struct.pack_into('>I', bnfm, 0x48, bone_chart_count)  
        struct.pack_into('>I', bnfm, 0x4C, len(strings_to_write)) 

        struct.pack_into('>I', bnfm, 0x50, 0)                 
        struct.pack_into('>I', bnfm, 0x54, 0)                  
        struct.pack_into('>I', bnfm, 0x58, bone_start)        
        struct.pack_into('>I', bnfm, 0x5C, poly_info_start)   
        
        struct.pack_into('>I', bnfm, 0x60, material_start)    
        struct.pack_into('>I', bnfm, 0x64, 0)                 
        struct.pack_into('>I', bnfm, 0x68, material_2_start)  
        struct.pack_into('>I', bnfm, 0x6C, 0)                 
        struct.pack_into('>I', bnfm, 0x74, string_start)      

        out_name = os.path.join(self.dir_path, f"{self.file_basename}.bnfm")
        with open(out_name, 'wb') as out_f:
            out_f.write(bnfm)
            
        print(f"Sucsess, size {os.path.basename(out_name)} ({len(bnfm)} bytes)")

if __name__ == "__main__":
    glb_files = glob.glob("*.glb") + glob.glob("*.GLB")
    glb_files = list(set(glb_files))
    
    if len(glb_files) == 0:
        print("nada glb found.")
    for file_path in glb_files:
        exporter = GLBExporter(os.path.abspath(file_path))
        exporter.convert()
