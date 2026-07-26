import json, time, random, zlib, math, hashlib


HARDWARE_PROFILES = [
    {
        "id": "win_intel_uhd620",
        "screenInfo": "1920-1080-1040-24-*-*-*",
        "screen": {"width": 1920, "height": 1080, "availHeight": 1040},
        "dpr": 1.0,
        "deviceMemory": 8,
        "hardwareConcurrency": 8,
        "plugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1920-1080-1040-24-*-*-*",
        "gpu": {
            "vendor": "Google Inc. (Intel)",
            "model": "ANGLE (Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "extensions": [
                'ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float',
                'EXT_depth_clamp', 'EXT_float_blend', 'EXT_frag_depth', 'EXT_shader_texture_lod',
                'EXT_sRGB', 'EXT_texture_compression_bptc', 'EXT_texture_compression_rgtc',
                'EXT_texture_filter_anisotropic', 'KHR_parallel_shader_compile',
                'OES_element_index_uint', 'OES_fbo_render_mipmap', 'OES_standard_derivatives',
                'OES_texture_float', 'OES_texture_float_linear', 'OES_texture_half_float',
                'OES_texture_half_float_linear', 'OES_vertex_array_object',
                'WEBGL_color_buffer_float', 'WEBGL_compressed_texture_s3tc',
                'WEBGL_compressed_texture_s3tc_srgb', 'WEBGL_debug_renderer_info',
                'WEBGL_debug_shaders', 'WEBGL_depth_texture', 'WEBGL_draw_buffers',
                'WEBGL_lose_context', 'WEBGL_multi_draw',
            ]
        },
        "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
        "canvas": {
            "hash": 1435301173,
            "histogramBins": [
                14051, 47, 77, 59, 38, 48, 32, 38, 45, 39, 42, 43, 49, 27, 38, 34, 31, 38, 26, 33,
                34, 40, 33, 18, 35, 30, 42, 29, 36, 35, 22, 42, 12, 35, 29, 48, 34, 34, 32, 27, 32, 37,
                26, 35, 23, 33, 20, 46, 24, 30, 12, 41, 17, 20, 34, 22, 14, 24, 26, 29, 23, 15, 15, 35,
                31, 17, 18, 24, 19, 27, 21, 22, 27, 13, 23, 20, 27, 27, 26, 25, 23, 27, 20, 29, 24, 26,
                17, 21, 12, 25, 18, 39, 33, 32, 27, 55, 34, 16, 51, 24, 54, 60, 421, 20, 22, 24, 15, 24,
                21, 25, 25, 22, 25, 28, 21, 26, 29, 40, 18, 17, 30, 14, 21, 22, 29, 19, 22, 76, 23, 18,
                25, 28, 35, 17, 27, 35, 32, 16, 35, 22, 25, 37, 22, 31, 22, 27, 22, 25, 25, 19, 15, 19,
                29, 62, 30, 32, 19, 14, 19, 14, 20, 19, 25, 35, 28, 13, 16, 14, 26, 21, 23, 26, 25, 27,
                37, 27, 29, 25, 26, 30, 29, 28, 13, 32, 18, 17, 23, 16, 27, 10, 31, 32, 30, 30, 11, 17,
                12, 19, 22, 20, 24, 34, 35, 35, 51, 50, 40, 36, 26, 23, 29, 28, 49, 31, 20, 24, 31, 27,
                41, 42, 26, 26, 21, 32, 55, 26, 40, 38, 48, 43, 33, 21, 23, 43, 43, 34, 37, 46, 54, 31,
                48, 35, 38, 39, 35, 48, 47, 55, 36, 60, 71, 44, 73, 85, 465, 13470
            ]
        },
    },
    {
        "id": "win_nvidia_gtx1650",
        "screenInfo": "1920-1080-1040-24-*-*-*",
        "screen": {"width": 1920, "height": 1080, "availHeight": 1040},
        "dpr": 1.0,
        "deviceMemory": 8,
        "hardwareConcurrency": 8,
        "plugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1920-1080-1040-24-*-*-*",
        "gpu": {
            "vendor": "Google Inc. (NVIDIA)",
            "model": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "extensions": [
                'ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float',
                'EXT_depth_clamp', 'EXT_disjoint_timer_query', 'EXT_float_blend', 'EXT_frag_depth',
                'EXT_shader_texture_lod', 'EXT_sRGB', 'EXT_texture_compression_bptc',
                'EXT_texture_compression_rgtc', 'EXT_texture_filter_anisotropic',
                'KHR_parallel_shader_compile', 'OES_element_index_uint', 'OES_fbo_render_mipmap',
                'OES_standard_derivatives', 'OES_texture_float', 'OES_texture_float_linear',
                'OES_texture_half_float', 'OES_texture_half_float_linear',
                'OES_vertex_array_object', 'WEBGL_color_buffer_float',
                'WEBGL_compressed_texture_s3tc', 'WEBGL_compressed_texture_s3tc_srgb',
                'WEBGL_debug_renderer_info', 'WEBGL_debug_shaders', 'WEBGL_depth_texture',
                'WEBGL_draw_buffers', 'WEBGL_lose_context', 'WEBGL_multi_draw',
            ]
        },
        "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
        "canvas": {
            "hash": -827765319,
            "histogramBins": [
                14120, 44, 80, 55, 40, 45, 35, 36, 48, 37, 40, 45, 47, 30, 36, 32, 33, 36, 28, 31,
                36, 38, 35, 20, 33, 32, 40, 31, 34, 37, 20, 44, 14, 33, 31, 46, 36, 32, 34, 25, 34, 35,
                28, 33, 25, 31, 22, 44, 26, 28, 14, 39, 19, 18, 36, 20, 16, 22, 28, 27, 25, 13, 17, 33,
                33, 15, 20, 22, 21, 25, 23, 20, 29, 11, 25, 18, 29, 25, 28, 23, 25, 25, 22, 27, 26, 24,
                19, 19, 14, 23, 20, 37, 35, 30, 29, 53, 36, 14, 53, 22, 56, 58, 418, 22, 20, 26, 13, 26,
                19, 27, 23, 24, 23, 30, 19, 28, 27, 42, 16, 19, 28, 16, 19, 24, 27, 21, 20, 78, 21, 20,
                23, 30, 33, 19, 25, 37, 30, 18, 33, 24, 23, 39, 20, 33, 20, 29, 20, 27, 23, 21, 13, 21,
                27, 64, 28, 34, 17, 16, 17, 16, 18, 21, 23, 37, 26, 15, 14, 16, 24, 23, 21, 28, 23, 29,
                35, 29, 27, 27, 24, 32, 27, 30, 11, 34, 16, 19, 21, 18, 25, 12, 29, 34, 28, 32, 9, 19,
                10, 21, 20, 22, 22, 36, 33, 37, 49, 52, 38, 38, 24, 25, 27, 30, 47, 33, 18, 26, 29, 29,
                39, 44, 24, 28, 19, 34, 53, 28, 38, 40, 46, 45, 31, 23, 21, 45, 41, 36, 35, 48, 52, 33,
                46, 37, 36, 41, 33, 50, 45, 57, 34, 62, 69, 46, 71, 87, 462, 13405
            ]
        },
    },
    {
        "id": "win_intel_iris_xe",
        "screenInfo": "1536-864-824-24-*-*-*",
        "screen": {"width": 1536, "height": 864, "availHeight": 824},
        "dpr": 1.25,
        "deviceMemory": 8,
        "hardwareConcurrency": 12,
        "plugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1536-864-824-24-*-*-*",
        "gpu": {
            "vendor": "Google Inc. (Intel)",
            "model": "ANGLE (Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "extensions": [
                'ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float',
                'EXT_depth_clamp', 'EXT_float_blend', 'EXT_frag_depth', 'EXT_shader_texture_lod',
                'EXT_sRGB', 'EXT_texture_compression_bptc', 'EXT_texture_compression_rgtc',
                'EXT_texture_filter_anisotropic', 'KHR_parallel_shader_compile',
                'OES_element_index_uint', 'OES_fbo_render_mipmap', 'OES_standard_derivatives',
                'OES_texture_float', 'OES_texture_float_linear', 'OES_texture_half_float',
                'OES_texture_half_float_linear', 'OES_vertex_array_object',
                'WEBGL_color_buffer_float', 'WEBGL_compressed_texture_astc',
                'WEBGL_compressed_texture_etc', 'WEBGL_compressed_texture_s3tc',
                'WEBGL_compressed_texture_s3tc_srgb', 'WEBGL_debug_renderer_info',
                'WEBGL_debug_shaders', 'WEBGL_depth_texture', 'WEBGL_draw_buffers',
                'WEBGL_lose_context', 'WEBGL_multi_draw',
            ]
        },
        "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
        "canvas": {
            "hash": 948720165,
            "histogramBins": [
                14080, 49, 75, 61, 36, 50, 30, 40, 43, 41, 40, 45, 47, 29, 36, 36, 29, 40, 24, 35,
                32, 42, 31, 20, 33, 32, 40, 31, 34, 37, 20, 44, 10, 37, 27, 50, 32, 36, 30, 29, 30, 39,
                24, 37, 21, 35, 18, 48, 22, 32, 10, 43, 15, 22, 32, 24, 12, 26, 24, 31, 21, 17, 13, 37,
                29, 19, 16, 26, 17, 29, 19, 24, 25, 15, 21, 22, 25, 29, 24, 27, 21, 29, 18, 31, 22, 28,
                15, 23, 10, 27, 16, 41, 31, 34, 25, 57, 32, 18, 49, 26, 52, 62, 423, 18, 24, 22, 17, 22,
                23, 23, 27, 20, 27, 26, 23, 24, 31, 38, 20, 15, 32, 12, 23, 20, 31, 17, 24, 74, 25, 16,
                27, 26, 37, 15, 29, 33, 34, 14, 37, 20, 27, 35, 24, 29, 24, 25, 24, 23, 27, 17, 17, 17,
                31, 60, 32, 30, 21, 12, 21, 12, 22, 17, 27, 33, 30, 11, 18, 12, 28, 19, 25, 24, 27, 25,
                39, 25, 31, 23, 28, 28, 31, 26, 15, 30, 20, 15, 25, 14, 29, 8, 33, 30, 32, 28, 13, 15,
                14, 17, 24, 18, 26, 32, 37, 33, 53, 48, 42, 34, 28, 21, 31, 26, 51, 29, 22, 22, 33, 25,
                43, 40, 28, 24, 23, 30, 57, 24, 42, 36, 50, 41, 35, 19, 25, 41, 45, 32, 39, 44, 56, 29,
                50, 33, 40, 37, 37, 46, 49, 53, 38, 58, 73, 42, 75, 83, 468, 13500
            ]
        },
    },
    {
        "id": "win_nvidia_rtx3060",
        "screenInfo": "2560-1440-1400-24-*-*-*",
        "screen": {"width": 2560, "height": 1440, "availHeight": 1400},
        "dpr": 1.0,
        "deviceMemory": 8,
        "hardwareConcurrency": 12,
        "plugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||2560-1440-1400-24-*-*-*",
        "gpu": {
            "vendor": "Google Inc. (NVIDIA)",
            "model": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "extensions": [
                'ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float',
                'EXT_depth_clamp', 'EXT_disjoint_timer_query', 'EXT_float_blend', 'EXT_frag_depth',
                'EXT_shader_texture_lod', 'EXT_sRGB', 'EXT_texture_compression_bptc',
                'EXT_texture_compression_rgtc', 'EXT_texture_filter_anisotropic',
                'KHR_parallel_shader_compile', 'OES_element_index_uint', 'OES_fbo_render_mipmap',
                'OES_standard_derivatives', 'OES_texture_float', 'OES_texture_float_linear',
                'OES_texture_half_float', 'OES_texture_half_float_linear',
                'OES_vertex_array_object', 'WEBGL_color_buffer_float',
                'WEBGL_compressed_texture_s3tc', 'WEBGL_compressed_texture_s3tc_srgb',
                'WEBGL_debug_renderer_info', 'WEBGL_debug_shaders', 'WEBGL_depth_texture',
                'WEBGL_draw_buffers', 'WEBGL_lose_context', 'WEBGL_multi_draw',
            ]
        },
        "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
        "canvas": {
            "hash": -1293847205,
            "histogramBins": [
                14015, 50, 74, 62, 35, 51, 29, 41, 42, 42, 39, 46, 46, 30, 35, 37, 28, 41, 23, 36,
                31, 43, 30, 21, 32, 33, 39, 32, 33, 38, 19, 45, 9, 38, 26, 51, 31, 37, 29, 30, 29, 40,
                23, 38, 20, 36, 17, 49, 21, 33, 9, 44, 14, 23, 31, 25, 11, 27, 23, 32, 20, 18, 12, 38,
                28, 20, 15, 27, 16, 30, 18, 25, 24, 16, 20, 23, 24, 30, 23, 28, 20, 30, 17, 32, 21, 29,
                14, 24, 9, 28, 15, 42, 30, 35, 24, 58, 31, 19, 48, 27, 51, 63, 424, 17, 25, 21, 18, 21,
                24, 22, 28, 19, 28, 25, 24, 23, 32, 37, 21, 14, 33, 11, 24, 19, 32, 16, 25, 73, 26, 15,
                28, 25, 38, 14, 30, 32, 35, 13, 38, 19, 28, 34, 25, 28, 25, 24, 25, 22, 28, 16, 18, 16,
                32, 59, 33, 29, 22, 11, 22, 11, 23, 16, 28, 32, 31, 10, 19, 11, 29, 18, 26, 23, 28, 24,
                40, 24, 32, 22, 29, 27, 32, 25, 16, 29, 21, 14, 26, 13, 30, 7, 34, 29, 33, 27, 14, 14,
                15, 16, 25, 17, 27, 31, 38, 32, 54, 47, 43, 33, 29, 20, 32, 25, 52, 28, 23, 21, 34, 24,
                44, 39, 29, 23, 24, 29, 58, 23, 43, 35, 51, 40, 36, 18, 26, 40, 46, 31, 40, 43, 57, 28,
                51, 32, 41, 36, 38, 45, 50, 52, 39, 57, 74, 41, 76, 82, 469, 13535
            ]
        },
    },
    {
        "id": "win_amd_radeon",
        "screenInfo": "1920-1080-1040-24-*-*-*",
        "screen": {"width": 1920, "height": 1080, "availHeight": 1040},
        "dpr": 1.0,
        "deviceMemory": 8,
        "hardwareConcurrency": 8,
        "plugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1920-1080-1040-24-*-*-*",
        "gpu": {
            "vendor": "Google Inc. (AMD)",
            "model": "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "extensions": [
                'ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float',
                'EXT_depth_clamp', 'EXT_float_blend', 'EXT_frag_depth', 'EXT_shader_texture_lod',
                'EXT_sRGB', 'EXT_texture_compression_bptc', 'EXT_texture_compression_rgtc',
                'EXT_texture_filter_anisotropic', 'KHR_parallel_shader_compile',
                'OES_element_index_uint', 'OES_fbo_render_mipmap', 'OES_standard_derivatives',
                'OES_texture_float', 'OES_texture_float_linear', 'OES_texture_half_float',
                'OES_texture_half_float_linear', 'OES_vertex_array_object',
                'WEBGL_color_buffer_float', 'WEBGL_compressed_texture_s3tc',
                'WEBGL_compressed_texture_s3tc_srgb', 'WEBGL_debug_renderer_info',
                'WEBGL_debug_shaders', 'WEBGL_depth_texture', 'WEBGL_draw_buffers',
                'WEBGL_lose_context', 'WEBGL_multi_draw',
            ]
        },
        "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
        "canvas": {
            "hash": 629481037,
            "histogramBins": [
                14090, 45, 79, 57, 40, 46, 34, 37, 47, 38, 41, 44, 48, 28, 37, 33, 32, 37, 27, 32,
                35, 39, 34, 19, 34, 31, 41, 30, 35, 36, 21, 43, 13, 34, 30, 47, 35, 33, 33, 26, 33, 36,
                27, 34, 24, 32, 21, 45, 25, 29, 13, 40, 18, 19, 35, 21, 15, 23, 27, 28, 24, 14, 16, 34,
                32, 16, 19, 23, 20, 26, 22, 21, 28, 12, 24, 19, 28, 26, 27, 24, 24, 26, 21, 28, 25, 25,
                18, 20, 13, 24, 19, 38, 34, 31, 28, 54, 35, 15, 52, 23, 55, 59, 420, 21, 21, 25, 14, 25,
                20, 26, 24, 23, 24, 29, 20, 27, 28, 41, 17, 18, 29, 15, 20, 23, 28, 20, 21, 77, 22, 19,
                24, 29, 34, 18, 26, 36, 31, 17, 34, 23, 24, 38, 21, 32, 21, 28, 21, 26, 24, 20, 14, 20,
                28, 63, 29, 33, 18, 15, 18, 15, 19, 20, 24, 36, 27, 14, 15, 15, 25, 22, 22, 27, 24, 28,
                36, 28, 28, 26, 25, 31, 28, 29, 12, 33, 17, 18, 22, 17, 26, 11, 30, 33, 29, 31, 10, 18,
                11, 20, 21, 21, 23, 35, 34, 36, 50, 51, 39, 37, 25, 24, 28, 29, 48, 32, 19, 25, 30, 28,
                40, 43, 25, 27, 20, 33, 54, 27, 39, 39, 47, 44, 32, 22, 22, 44, 42, 35, 36, 47, 53, 32,
                47, 36, 37, 40, 34, 49, 46, 56, 35, 61, 70, 45, 72, 86, 464, 13440
            ]
        },
    },
    {
        "id": "win_intel_hd400",
        "screenInfo": "1366-768-728-24-*-*-*",
        "screen": {"width": 1366, "height": 768, "availHeight": 728},
        "dpr": 1.0,
        "deviceMemory": 4,
        "hardwareConcurrency": 4,
        "plugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1366-768-728-24-*-*-*",
        "gpu": {
            "vendor": "Google Inc. (Intel)",
            "model": "ANGLE (Intel(R) HD Graphics 400 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "extensions": [
                'ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float',
                'EXT_depth_clamp', 'EXT_float_blend', 'EXT_frag_depth', 'EXT_shader_texture_lod',
                'EXT_sRGB', 'EXT_texture_compression_bptc', 'EXT_texture_compression_rgtc',
                'EXT_texture_filter_anisotropic', 'OES_element_index_uint', 'OES_fbo_render_mipmap',
                'OES_standard_derivatives', 'OES_texture_float', 'OES_texture_float_linear',
                'OES_texture_half_float', 'OES_texture_half_float_linear', 'OES_vertex_array_object',
                'WEBGL_color_buffer_float', 'WEBGL_compressed_texture_s3tc',
                'WEBGL_compressed_texture_s3tc_srgb', 'WEBGL_debug_renderer_info',
                'WEBGL_debug_shaders', 'WEBGL_depth_texture', 'WEBGL_draw_buffers',
                'WEBGL_lose_context',
            ]
        },
        "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
        "canvas": {
            "hash": 1435301173,
            "histogramBins": [
                14051, 47, 77, 59, 38, 48, 32, 38, 45, 39, 42, 43, 49, 27, 38, 34, 31, 38, 26, 33,
                34, 40, 33, 18, 35, 30, 42, 29, 36, 35, 22, 42, 12, 35, 29, 48, 34, 34, 32, 27, 32, 37,
                26, 35, 23, 33, 20, 46, 24, 30, 12, 41, 17, 20, 34, 22, 14, 24, 26, 29, 23, 15, 15, 35,
                31, 17, 18, 24, 19, 27, 21, 22, 27, 13, 23, 20, 27, 27, 26, 25, 23, 27, 20, 29, 24, 26,
                17, 21, 12, 25, 18, 39, 33, 32, 27, 55, 34, 16, 51, 24, 54, 60, 421, 20, 22, 24, 15, 24,
                21, 25, 25, 22, 25, 28, 21, 26, 29, 40, 18, 17, 30, 14, 21, 22, 29, 19, 22, 76, 23, 18,
                25, 28, 35, 17, 27, 35, 32, 16, 35, 22, 25, 37, 22, 31, 22, 27, 22, 25, 25, 19, 15, 19,
                29, 62, 30, 32, 19, 14, 19, 14, 20, 19, 25, 35, 28, 13, 16, 14, 26, 21, 23, 26, 25, 27,
                37, 27, 29, 25, 26, 30, 29, 28, 13, 32, 18, 17, 23, 16, 27, 10, 31, 32, 30, 30, 11, 17,
                12, 19, 22, 20, 24, 34, 35, 35, 51, 50, 40, 36, 26, 23, 29, 28, 49, 31, 20, 24, 31, 27,
                41, 42, 26, 26, 21, 32, 55, 26, 40, 38, 48, 43, 33, 21, 23, 43, 43, 34, 37, 46, 54, 31,
                48, 35, 38, 39, 35, 48, 47, 55, 36, 60, 71, 44, 73, 85, 465, 13470
            ]
        },
    },
]

DOMAIN_TIMEZONE = {
    'amazon.com': -6,
    'amazon.ca': -5,
    'amazon.com.mx': -6,
}


class FwcimAmazon:
    __KEY_IDENTIFIER = "ECdITeCs"
    __KEY_MATERIAL = [1888420705, 2576816180, 2347232058, 874813317]
    __XXTEA_DELTA = 0x9E3779B9

    __MAX_KEY_INTERVALS = 9
    __MAX_KEY_CYCLES = 10
    __MAX_CLICK_POSITIONS = 10

    REAL_METRICS_BASE = {
        "el": 1, "script": 0, "h": 0, "batt": 0, "perf": 0, "auto": 0, "tz": 0,
        "fp2": 0, "lsubid": 0, "browser": 0, "capabilities": 0, "gpu": 0, "dnt": 0,
        "math": 0, "tts": 0, "input": 0, "canvas": 0, "captchainput": 0, "pow": 0
    }

    _session_lsubid = None
    _session_profile = None

    def __init__(
        self,
        location: str,
        userAgent: str,
        referrer: str = "",
        dynamicUrls: list = None,
        inlineHashes: list = None,
        canvasHash: int = None,
        canvasEmailHash: int = None,
        emailValue: str = "",
        customerName: str = "",
        lsUbid: str = None,
        timezone: int = None,
    ) -> None:
        self.__location = location
        self.__userAgent = userAgent
        self.__referrer = referrer
        self.__dynamicUrls = dynamicUrls or []
        self.__inlineHashes = inlineHashes or []
        self.__canvasHash = canvasHash
        self.__canvasEmailHash = canvasEmailHash
        self.__emailValue = emailValue
        self.__customerName = customerName
        self.__start_timestamp = int(time.time() * 1000)

        self.__timezone = timezone if timezone is not None else self.__detect_timezone(location)

        if FwcimAmazon._session_profile:
            self.__profile = FwcimAmazon._session_profile
        else:
            self.__profile = random.choice(HARDWARE_PROFILES)
            FwcimAmazon._session_profile = self.__profile

        if lsUbid:
            self.__lsUbid = lsUbid
        elif FwcimAmazon._session_lsubid:
            self.__lsUbid = FwcimAmazon._session_lsubid
        else:
            self.__lsUbid = self.__generate_lsubid()
            FwcimAmazon._session_lsubid = self.__lsUbid

    @classmethod
    def reset_session(cls):
        cls._session_lsubid = None
        cls._session_profile = None

    def generateMetadata(self) -> dict:
        try:
            fingerprint = self.__build_fingerprint()
            json_str = json.dumps(fingerprint, separators=(',', ':'))

            crc = format(zlib.crc32(json_str.encode('utf-8')) & 0xFFFFFFFF, '08X')
            payload = f"{crc}#{json_str}"
            encrypted = self.__xxtea_encrypt(payload, self.__KEY_MATERIAL)
            b64 = self.__base64_encode(encrypted)
            md = f"{self.__KEY_IDENTIFIER}:{b64}"

            return {'status': True, 'metadata1': md}
        except Exception as error:
            return {'status': False, 'description': str(error)}


    def __build_fingerprint(self) -> dict:
        p = self.__profile
        form = self.__build_form()

        form_clicks = sum(f["clicks"] for f in form.values())
        form_keypresses = sum(f["keyPresses"] for f in form.values())

        extra_clicks = random.randint(1, 3)
        total_clicks = form_clicks + extra_clicks
        total_keypresses = form_keypresses

        all_key_intervals = []
        all_key_cycles = []
        for field in form.values():
            all_key_intervals.extend(field["keyPressTimeIntervals"])
            all_key_cycles.extend(field["keyCycles"])

        global_key_intervals = [max(1, v + random.randint(-3, 3)) for v in all_key_intervals[-self.__MAX_KEY_INTERVALS:]]
        global_key_cycles = [max(1, v + random.randint(-10, 10)) for v in all_key_cycles[-self.__MAX_KEY_CYCLES:]]

        all_click_positions = []
        for field in form.values():
            all_click_positions.extend(field["mouseClickPositions"])
        for _ in range(extra_clicks):
            x = random.randint(260, 600)
            y = random.randint(180, 580)
            all_click_positions.append(f"{x},{y}")
        if random.random() < 0.3:
            all_click_positions.append("0,0")
        all_click_positions = all_click_positions[-self.__MAX_CLICK_POSITIONS:]

        all_mouse_cycles = []
        for field in form.values():
            all_mouse_cycles.extend(field["mouseCycles"])
        all_mouse_cycles = [max(1, v + random.randint(-10, 10)) for v in all_mouse_cycles]
        cycles_for_extra = max(0, extra_clicks - random.randint(0, 1))
        all_mouse_cycles.extend([random.randint(50, 300) for _ in range(cycles_for_extra)])

        interaction_total = sum(global_key_intervals) + sum(all_mouse_cycles)
        total_focus_time = sum(f.get("totalFocusTime", 0) for f in form.values())
        time_to_submit = interaction_total + total_focus_time + random.randint(900, 2200)
        end = self.__start_timestamp + time_to_submit

        metrics = self.__build_metrics()
        script_elapsed = max(6, min(40, metrics.get("script", 0) + random.randint(6, 30)))
        canvas = self.__build_canvas()

        screen_info = p["screenInfo"]
        plugins_str = p["plugins"]
        duped_plugins_str = plugins_str

        fingerprint = {
            "metrics": metrics,
            "start": self.__start_timestamp,
            "interaction": {
                "clicks": total_clicks,
                "touches": 0,
                "keyPresses": total_keypresses,
                "cuts": sum(f.get("cuts", 0) for f in form.values()),
                "copies": 0,
                "pastes": sum(f.get("pastes", 0) for f in form.values()),
                "keyPressTimeIntervals": global_key_intervals,
                "mouseClickPositions": all_click_positions,
                "keyCycles": global_key_cycles,
                "mouseCycles": all_mouse_cycles,
                "touchCycles": []
            },
            "scripts": {
                "dynamicUrls": self.__dynamicUrls,
                "inlineHashes": self.__inlineHashes,
                "elapsed": script_elapsed,
                "dynamicUrlCount": len(self.__dynamicUrls),
                "inlineHashesCount": len(self.__inlineHashes)
            },
            "history": {"length": random.randint(3, 8)},
            "performance": {"timing": self.__build_performance_timing(end)},
            "automation": {
                "wd": {"properties": {"document": [], "window": [], "navigator": []}},
                "phantom": {"properties": {"window": []}}
            },
            "end": end,
            "timeZone": self.__timezone,
            "flashVersion": None,
            "plugins": plugins_str,
            "dupedPlugins": duped_plugins_str,
            "screenInfo": screen_info,
            "lsUbid": self.__lsUbid,
            "referrer": self.__referrer,
            "userAgent": self.__userAgent,
            "location": self.__location,
            "webDriver": False,
            "capabilities": {
                "css": {
                    "textShadow": 1, "WebkitTextStroke": 1, "boxShadow": 1, "borderRadius": 1,
                    "borderImage": 1, "opacity": 1, "transform": 1, "transition": 1
                },
                "js": {
                    "audio": True, "geolocation": True, "localStorage": "supported",
                    "touch": False, "video": True, "webWorker": True
                },
                "elapsed": random.choice([0, 1, 2])
            },
            "gpu": p["gpu"].copy(),
            "dnt": None,
            "math": p["math"].copy(),
        }

        fingerprint["timeToSubmit"] = time_to_submit
        fingerprint["form"] = form
        fingerprint["canvas"] = canvas
        fingerprint["token"] = {"isCompatible": True, "pageHasCaptcha": 0}
        fingerprint["auth"] = {"form": {"method": "post"}}
        fingerprint["errors"] = []
        fingerprint["version"] = "4.0.0"

        return fingerprint


    def __build_performance_timing(self, end_timestamp: int) -> dict:
        nav_start = self.__start_timestamp - random.randint(2500, 3800)
        fetch_offset = random.randint(10, 25)
        fetch_start = nav_start + fetch_offset

        dns_start = fetch_start
        dns_end = fetch_start
        connect_start = fetch_start
        connect_end = fetch_start
        secure_start = fetch_start

        request_start = fetch_start + random.randint(50, 100)
        response_start = request_start + random.randint(180, 300)
        response_end = response_start + random.randint(0, 250)
        dom_loading = response_end + random.randint(80, 180)
        unload_start = dom_loading + random.randint(0, 1)
        unload_end = unload_start + random.randint(15, 45)
        dom_interactive = dom_loading + random.randint(700, 1200)
        dom_content_start = dom_interactive + random.randint(20, 60)
        dom_content_end = dom_content_start + random.randint(2, 8)
        dom_complete = dom_interactive + random.randint(800, 1200)
        load_event_start = dom_complete + random.randint(0, 2)
        load_event_end = load_event_start + random.randint(30, 60)

        if load_event_end > end_timestamp:
            load_event_end = end_timestamp - random.randint(20, 120)
            load_event_start = max(dom_complete, load_event_end - random.randint(10, 50))

        return {
            "navigationStart": nav_start,
            "unloadEventStart": unload_start,
            "unloadEventEnd": unload_end,
            "redirectStart": 0,
            "redirectEnd": 0,
            "fetchStart": fetch_start,
            "domainLookupStart": dns_start,
            "domainLookupEnd": dns_end,
            "connectStart": connect_start,
            "connectEnd": connect_end,
            "secureConnectionStart": secure_start,
            "requestStart": request_start,
            "responseStart": response_start,
            "responseEnd": response_end,
            "domLoading": dom_loading,
            "domInteractive": dom_interactive,
            "domContentLoadedEventStart": dom_content_start,
            "domContentLoadedEventEnd": dom_content_end,
            "domComplete": dom_complete,
            "loadEventStart": load_event_start,
            "loadEventEnd": load_event_end
        }


    def __build_canvas(self) -> dict:
        p = self.__profile
        canvas_hash = self.__canvasHash if self.__canvasHash is not None else p["canvas"]["hash"]

        if self.__canvasEmailHash is not None:
            email_hash = self.__canvasEmailHash
        elif self.__emailValue:
            seed = f"canvas_email:{canvas_hash}:{self.__emailValue.upper()}"
            email_hash = zlib.crc32(seed.encode('utf-8'))
            if email_hash >= 0x80000000:
                email_hash -= 0x100000000
        else:
            email_hash = 0

        bin_rng = random.Random(f"bins:{canvas_hash}:{self.__lsUbid}")
        base_bins = p["canvas"]["histogramBins"][:]
        bins = []
        for i, v in enumerate(base_bins):
            if i == 0 or i == len(base_bins) - 1:
                bins.append(v + bin_rng.randint(-200, 200))
            elif v > 100:
                bins.append(v + bin_rng.randint(-4, 4))
            else:
                bins.append(max(0, v + bin_rng.randint(-3, 3)))
        bins[0] += (36000 - sum(bins))

        return {
            "hash": canvas_hash,
            "emailHash": email_hash,
            "histogramBins": bins
        }


    def __build_metrics(self) -> dict:
        base = self.REAL_METRICS_BASE.copy()
        jittered = {}
        for key, value in base.items():
            if key in {"tz", "captchainput"}:
                jittered[key] = value
                continue
            r = random.random()
            if r < 0.60:
                jittered[key] = 0
            elif r < 0.85:
                jittered[key] = 1
            elif r < 0.95:
                jittered[key] = 2
            else:
                jittered[key] = 3
        return jittered


    def __build_form(self) -> dict:
        email_clicks = random.randint(2, 3)
        email_keypresses = random.randint(3, 10)
        email = self.__build_form_field(email_clicks, email_keypresses, 312, 32, prefilled_edit=True)
        email["totalFocusTime"] = random.randint(5000, 17000)
        email["cuts"] = random.choice([0, 0, 1])
        email["pastes"] = random.choice([0, 1, 1])
        if self.__emailValue:
            email["checksum"] = format(zlib.crc32(self.__emailValue.encode('utf-8')) & 0xFFFFFFFF, '08X')
        email["autocomplete"] = False
        email["prefilled"] = True

        name_clicks = random.randint(1, 5)
        name_keypresses = random.randint(8, 22)
        ap_customer_name = self.__build_form_field(name_clicks, name_keypresses, 312, 32)
        if self.__customerName:
            ap_customer_name["checksum"] = format(zlib.crc32(self.__customerName.encode('utf-8')) & 0xFFFFFFFF, '08X')
        ap_customer_name["autocomplete"] = False
        ap_customer_name["prefilled"] = False

        password_keypresses = random.randint(10, 32)
        password = self.__build_form_field(random.randint(0, 1), password_keypresses, 312, 32)
        password["autocomplete"] = False
        password["prefilled"] = False

        ap_password_check = self.__build_form_field(0, random.randint(10, 29), 312, 32)
        ap_password_check["autocomplete"] = False
        ap_password_check["prefilled"] = False

        return {
            "email": email,
            "ap_customer_name": ap_customer_name,
            "password": password,
            "ap_password_check": ap_password_check
        }


    def __build_form_field(self, clicks, keypresses, width, height, prefilled_edit=False):
        num_intervals = min(max(0, keypresses - 1), self.__MAX_KEY_INTERVALS)
        num_cycles = min(keypresses, self.__MAX_KEY_CYCLES)

        key_intervals = []
        if prefilled_edit:
            for i in range(num_intervals):
                raw = random.choice([
                    random.randint(8, 60),
                    random.randint(100, 500),
                    random.randint(800, 1700),
                ])
                key_intervals.append(raw)
        else:
            for i in range(num_intervals):
                if i == 0:
                    raw = self.__log_logistic_sample(alpha=220, beta=3.0)
                    raw = max(120, min(420, int(raw)))
                else:
                    raw = self.__log_logistic_sample(alpha=105, beta=3.5)
                    raw = max(27, min(400, int(raw)))
                key_intervals.append(int(raw))

        key_cycles = []
        if prefilled_edit:
            for i in range(num_cycles):
                raw = random.choice([
                    random.randint(60, 200),
                    random.randint(400, 1500),
                    random.randint(1800, 2500),
                ])
                key_cycles.append(raw)
        else:
            for i in range(num_cycles):
                if i == 0:
                    raw = self.__log_logistic_sample(alpha=250, beta=5.0)
                    raw = max(210, min(285, int(raw)))
                else:
                    raw = self.__log_logistic_sample(alpha=90, beta=3.5)
                    raw = max(55, min(220, int(raw)))
                key_cycles.append(int(raw))

        mouse_positions = []
        for _ in range(clicks):
            x = round(random.uniform(40, width - 20), 1)
            y_raw = random.uniform(-15, height - 4)
            y = round(y_raw, 0) if random.random() < 0.6 else round(y_raw, 1)
            mouse_positions.append(f"{x:g},{y:g}")

        mouse_cycles = []
        for _ in range(clicks):
            if random.random() < 0.08:
                mouse_cycles.append(random.randint(500, 1300))
            elif random.random() < 0.15:
                mouse_cycles.append(random.randint(3, 50))
            else:
                mouse_cycles.append(random.randint(60, 200))

        if keypresses > 0:
            focus_time = sum(key_intervals) + sum(mouse_cycles) + random.randint(400, 1500)
        elif clicks > 0:
            focus_time = sum(mouse_cycles) + random.randint(1500, 3000)
        else:
            focus_time = 0

        return {
            "clicks": clicks,
            "touches": 0,
            "keyPresses": keypresses,
            "cuts": 0,
            "copies": 0,
            "pastes": 0,
            "keyPressTimeIntervals": key_intervals,
            "mouseClickPositions": mouse_positions,
            "keyCycles": key_cycles,
            "mouseCycles": mouse_cycles,
            "touchCycles": [],
            "width": width,
            "height": height,
            "totalFocusTime": focus_time,
        }


    @staticmethod
    def __detect_timezone(url: str) -> int:
        for domain, tz in sorted(DOMAIN_TIMEZONE.items(), key=lambda x: -len(x[0])):
            if domain in url:
                return tz
        return -6

    @staticmethod
    def __log_logistic_sample(alpha=130, beta=3.5):
        u = random.random()
        u = max(0.005, min(0.995, u))
        return alpha * (u / (1 - u)) ** (1 / beta)

    def __generate_lsubid(self) -> str:
        part1 = f"X{random.randint(10, 99)}"
        part2 = f"{random.randint(1000000, 9999999)}"
        part3 = f"{random.randint(1000000, 9999999)}"
        part4 = f"{int(time.time())}"
        return f"{part1}-{part2}-{part3}:{part4}"


    def __xxtea_encrypt(self, data: str, key: list) -> str:
        if len(data) == 0:
            return ''

        n = math.ceil(len(data) / 4)
        v = []
        for i in range(n):
            word = 0
            for j in range(4):
                idx = i * 4 + j
                if idx < len(data):
                    word |= ord(data[idx]) << (j * 8)
            v.append(word)

        n = len(v)
        rounds = 6 + 52 // n
        total = 0
        z = v[n - 1]

        for _ in range(rounds):
            total = (total + self.__XXTEA_DELTA) & 0xFFFFFFFF
            e = (total >> 2) & 3
            for p in range(n):
                y = v[(p + 1) % n]
                mx = (((z >> 5) ^ (y << 2)) + ((y >> 3) ^ (z << 4))) ^ ((total ^ y) + (key[(p & 3) ^ e] ^ z))
                v[p] = (v[p] + mx) & 0xFFFFFFFF
                z = v[p]

        result = []
        for word in v:
            for j in range(4):
                result.append(chr((word >> (j * 8)) & 0xFF))
        return ''.join(result)

    def __base64_encode(self, data: str) -> str:
        import base64
        return base64.b64encode(data.encode('latin-1')).decode('utf-8')
