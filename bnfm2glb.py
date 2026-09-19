import struct
import os
import glob
import json

class BNFMImporter:
    def __init__(self, filepath):
        self.filepath = filepath
        self.dir_path = os.path.dirname(filepath)
        self.file_basename = os.path.splitext(os.path.basename(filepath))[0]
        self.file = None

        self.bones = []
        self.polygons = []

    def read_be_long(self):
        return struct.unpack('>I', self.file.read(4))[0]

    def read_be_short(self):
        return struct.unpack('>H', self.file.read(2))[0]

    def read_be_float(self):
        return struct.unpack('>f', self.file.read(4))[0]

    def read_be_half_float(self):
        return struct.unpack('>e', self.file.read(2))[0]

    def read_string(self):
        chars = []
        while True:
            char = self.file.read(1)
            if char == b'\x00' or char == b'':
                break
            chars.append(char.decode('utf-8', errors='ignore'))
        return "".join(chars)

    def parse(self):
        if not os.path.exists(self.filepath):
            print(f"nada, dis the right dir? {self.filepath}")
            return

        with open(self.filepath, 'rb') as self.file:
            header_check = self.read_be_long()
            header_start = self.read_be_long()
            self.file.seek(4, 1) 
            face_start = self.read_be_long()

            face_total = self.read_be_long() // 6
            vert_count_total = self.read_be_long() // 44
            bone_chart_start = self.read_be_long()
            self.file.seek(4, 1) 

            vert_start = self.read_be_long()
            face_start_b = self.read_be_long()
            self.file.seek(4, 1) 
            poly_name_count = self.read_be_long()

            bone_count = self.read_be_long()
            poly_count = self.read_be_long()
            mat_count = self.read_be_long() // 6
            poly_name_count_b = self.read_be_long()

            poly_name_count_c = self.read_be_long()
            bone_chart_count = self.read_be_long()
            bone_chart_count_b = self.read_be_long()
            string_count = self.read_be_long()

            unknown_start = self.read_be_long()
            self.file.seek(4, 1) 
            bone_start = self.read_be_long()
            poly_info_start = self.read_be_long()

            material_start = self.read_be_long()
            unknown_start_2 = self.read_be_long()
            material_2_start = self.read_be_long()
            bone_matrix_start = self.read_be_long()

            self.file.seek(4, 1) 
            string_start = self.read_be_long()

            self.file.seek(bone_start)
            bone_names = []
            
            for _ in range(bone_count):
                bone_name_start = self.read_be_long()
                return_pos = self.file.tell()
                
                self.file.seek(bone_name_start)
                bone_name = self.read_string()
                bone_names.append(bone_name)
                
                self.file.seek(return_pos)
                self.file.seek(4, 1)
                
                bone_parent_name_start = self.read_be_long()
                return_pos = self.file.tell()
                self.file.seek(bone_parent_name_start)
                bone_parent_name = self.read_string()
                
                self.file.seek(return_pos)
                
                bone_parent_idx = -1
                for idx, name in enumerate(bone_names):
                    if bone_parent_name == name:
                        bone_parent_idx = idx
                        break
                        
                self.file.seek(0x18, 1)
                pos = (self.read_be_float(), self.read_be_float(), self.read_be_float())
                scale = (self.read_be_float(), self.read_be_float(), self.read_be_float())
                
                self.file.seek(0x14, 1)
                matrix = [self.read_be_float() for _ in range(32)] 
                self.file.seek(0x0C, 1)

                self.bones.append({
                    "name": bone_name,
                    "parent_index": bone_parent_idx,
                    "parent_name": bone_parent_name,
                    "position": pos,
                    "scale": scale,
                    "matrix_data": matrix
                })

            self.file.seek(poly_info_start)
            poly_meta = []
            for _ in range(poly_count):
                meta = {
                    "poly_name_start": self.read_be_long(),
                    "skip": self.file.seek(4, 1),
                    "bone_chart_start": self.read_be_long(),
                    "poly_start": self.read_be_long(),
                    "skip2": self.file.seek(8, 1),
                    "face_count": self.read_be_long() // 3,
                    "poly_vert_count": self.read_be_long(),
                    "bone_id_count": self.read_be_long(),
                    "mat_id": self.read_be_long(),
                    "skip3": self.file.seek(8, 1)
                }
                poly_meta.append(meta)

            mat_name_start_array = []
            mat2_name_start_array = []
            
            self.file.seek(material_start)
            for _ in range(mat_count):
                mat_name_start_array.append(self.read_be_long())
                self.file.seek(0x110, 1)
                mat2_name_start_array.append(self.read_be_long())
                self.file.seek(0x110, 1)

            poly_name_array = []
            self.file.seek(material_2_start)
            for _ in range(mat_count):
                poly_name_start = self.read_be_long()
                return_pos = self.file.tell()
                self.file.seek(poly_name_start)
                poly_name_array.append(self.read_string())
                self.file.seek(return_pos)
                self.file.seek(0x38, 1)

            vert_return = vert_start

            for z in range(poly_count):
                current_poly = poly_meta[z]
                
                bone_chart_array = []
                self.file.seek(current_poly["bone_chart_start"])
                for _ in range(bone_chart_count):
                    bone_chart_array.append(self.read_be_long() + 1)

                vert_array = []
                uv_array = []
                uv2_array = []
                color_array = []
                b0_array = []
                w1_array = []

                if current_poly["poly_vert_count"] != 0:
                    self.file.seek(vert_return)
                    for _ in range(current_poly["poly_vert_count"]):
                        vx, vy, vz = self.read_be_float(), self.read_be_float(), self.read_be_float()
                        self.file.seek(4, 1) 
                        
                        cr, cg, cb, ca = struct.unpack('4B', self.file.read(4))
                        tu, tv = self.read_be_half_float(), self.read_be_half_float()
                        tu2, tv2 = self.read_be_half_float(), self.read_be_half_float()
                        
                        b1, b2, b3, b4 = struct.unpack('4B', self.file.read(4))
                        w1_val, w2_val, w3_val, w4_val = struct.unpack('4B', self.file.read(4))
                        
                        self.file.seek(8, 1) 

                        vert_array.append([vx, vy, vz])
                        uv_array.append([tu, tv])
                        uv2_array.append([tu2, tv2])
                        color_array.append([cr / 255.0, cg / 255.0, cb / 255.0, ca / 255.0])
                        
                        b0_array.append([b1 + 1, b2 + 1, b3 + 1, b4 + 1])
                        w1_array.append([w1_val / 255.0, w2_val / 255.0, w3_val / 255.0, w4_val / 255.0])
                    
                    vert_return = self.file.tell()

                face_array = []
                self.file.seek(face_start)
                self.file.seek(current_poly["poly_start"], 1)
                for _ in range(current_poly["face_count"]):
                    fa = self.read_be_short()
                    fb = self.read_be_short()
                    fc = self.read_be_short()
                    face_array.append([fa, fb, fc])

                b1_array = []
                for x in range(len(vert_array)):
                    mapped_bones = []
                    for imp_bone in b0_array[x]:
                        if imp_bone - 1 < len(bone_chart_array):
                            b_id = bone_chart_array[imp_bone - 1]
                        else:
                            b_id = 1
                        if b_id > bone_count:
                            b_id = 1
                        mapped_bones.append(b_id - 1) 
                    b1_array.append(mapped_bones)

                mat_id = 1
                self.file.seek(current_poly["poly_name_start"])
                poly_name = self.read_string()
                limit = min(poly_name_count, len(poly_name_array))
                for y in range(limit):
                    if poly_name == poly_name_array[y]:
                        mat_id = y + 1
                        break

                if 0 <= (mat_id - 1) < len(mat_name_start_array):
                    self.file.seek(mat_name_start_array[mat_id - 1])
                    mat_name = self.read_string()
                else:
                    mat_name = f"Fallback_Material_{mat_id}"

                if 0 <= (mat_id - 1) < len(mat2_name_start_array):
                    self.file.seek(mat2_name_start_array[mat_id - 1])
                    mat2_name = self.read_string()
                else:
                    mat2_name = ""


                self.polygons.append({
                    "name": poly_name,
                    "vertices": vert_array,
                    "faces": face_array,
                    "uvs": uv_array,
                    "uvs_layer2": uv2_array,
                    "vertex_colors": color_array,
                    "bone_indices": b1_array,
                    "bone_weights": w1_array,
                    "material_name": mat_name,
                    "material_name_layer2": mat2_name if mat2_name else None
                })
                
        self.export_glb()

    def export_glb(self):
        bin_buffer = bytearray()
        
        gltf = {
            "asset": {"version": "2.0", "generator": "bnfm2glb"},
            "scene": 0,
            "scenes": [{"nodes": []}],
            "nodes": [],
            "meshes": [],
            "bufferViews": [],
            "accessors": []
        }

        bone_node_indices = []
        for i, b in enumerate(self.bones):
            node_idx = len(gltf["nodes"])
            bone_node_indices.append(node_idx)
            
            node = {
                "name": b["name"],
                "translation": [b["position"][0], b["position"][1], b["position"][2]],
                "scale": [b["scale"][0], b["scale"][1], b["scale"][2]],
                "children": []
            }
            gltf["nodes"].append(node)

        for i, b in enumerate(self.bones):
            p_idx = b["parent_index"]
            if p_idx != -1 and p_idx < len(bone_node_indices):
                gltf["nodes"][bone_node_indices[p_idx]]["children"].append(bone_node_indices[i])
            else:
                gltf["scenes"][0]["nodes"].append(bone_node_indices[i])

        for poly in self.polygons:
            if not poly["vertices"]:
                continue
                
            mesh_idx = len(gltf["meshes"])
            node_mesh_idx = len(gltf["nodes"])
            
            gltf["scenes"][0]["nodes"].append(node_mesh_idx)
            gltf["nodes"].append({
                "name": poly["name"],
                "mesh": mesh_idx
            })

            v_offset = len(bin_buffer)
            for v in poly["vertices"]:
                bin_buffer.extend(struct.pack('fff', *v))
            v_length = len(bin_buffer) - v_offset
            v_view = len(gltf["bufferViews"])
            gltf["bufferViews"].append({"buffer": 0, "byteOffset": v_offset, "byteLength": v_length, "target": 34962})
            v_acc = len(gltf["accessors"])
            gltf["accessors"].append({
                "bufferView": v_view, "byteOffset": 0, "componentType": 5126, "count": len(poly["vertices"]),
                "type": "VEC3", "max": [max(v[0] for v in poly["vertices"]), max(v[1] for v in poly["vertices"]), max(v[2] for v in poly["vertices"])],
                "min": [min(v[0] for v in poly["vertices"]), min(v[1] for v in poly["vertices"]), min(v[2] for v in poly["vertices"])]
            })

            uv_offset = len(bin_buffer)
            for uv in poly["uvs"]:
                bin_buffer.extend(struct.pack('ff', uv[0], 1.0 - uv[1]))
            uv_length = len(bin_buffer) - uv_offset
            uv_view = len(gltf["bufferViews"])
            gltf["bufferViews"].append({"buffer": 0, "byteOffset": uv_offset, "byteLength": uv_length, "target": 34962})
            uv_acc = len(gltf["accessors"])
            gltf["accessors"].append({
                "bufferView": uv_view, "byteOffset": 0, "componentType": 5126, "count": len(poly["uvs"]), "type": "VEC2"
            })

            f_offset = len(bin_buffer)
            for f in poly["faces"]:
                bin_buffer.extend(struct.pack('HHH', *f))
            while len(bin_buffer) % 4 != 0:
                bin_buffer.append(0)
            f_length = len(bin_buffer) - f_offset
            f_view = len(gltf["bufferViews"])
            gltf["bufferViews"].append({"buffer": 0, "byteOffset": f_offset, "byteLength": f_length, "target": 34963})
            f_acc = len(gltf["accessors"])
            gltf["accessors"].append({
                "bufferView": f_view, "byteOffset": 0, "componentType": 5123, "count": len(poly["faces"]) * 3, "type": "SCALAR"
            })

            gltf["meshes"].append({
                "name": poly["name"],
                "primitives": [{
                    "attributes": {"POSITION": v_acc, "TEXCOORD_0": uv_acc},
                    "indices": f_acc
                }]
            })

        if bin_buffer:
            gltf["buffers"] = [{"byteLength": len(bin_buffer)}]

        json_str = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
        while len(json_str) % 4 != 0:
            json_str += b' '

        while len(bin_buffer) % 4 != 0:
            bin_buffer.append(0)

        glb_out = bytearray()
        glb_out.extend(b'glTF')
        glb_out.extend(struct.pack('I', 2))
        total_size = 12 + 8 + len(json_str) + 8 + len(bin_buffer)
        glb_out.extend(struct.pack('I', total_size))

        glb_out.extend(struct.pack('I', len(json_str)))
        glb_out.extend(b'JSON')
        glb_out.extend(json_str)

        glb_out.extend(struct.pack('I', len(bin_buffer)))
        glb_out.extend(b'BIN\x00')
        glb_out.extend(bin_buffer)

        out_name = os.path.join(self.dir_path, f"{self.file_basename}.glb")
        with open(out_name, 'wb') as out_f:
            out_f.write(glb_out)
        print(f"Sucsess {os.path.basename(out_name)}")

if __name__ == "__main__":
    bnfm_files = glob.glob("*.bnfm") + glob.glob("*.BNFM")
    
    bnfm_files = list(set(bnfm_files)) 

    print(f"found {len(bnfm_files)} .bnfm file(s)")
    
    if len(bnfm_files) == 0:
        print("\n Manual")
        all_files = os.listdir(".")
        for f in all_files:
            if f.lower().endswith(".bnfm"):
                bnfm_files.append(f)
                
    if len(bnfm_files) == 0:
        print("Nothing")
        print(os.listdir("."))
    else:
        for file_path in bnfm_files:
            print(f"Process {os.path.basename(file_path)}")
            importer = BNFMImporter(os.path.abspath(file_path))
            importer.parse()
        print("Finish")
