import unittest
from PIL import Image, ImageDraw
from photo_bands import layout, render_strips, preview_image, resolve_render


class LayoutTest(unittest.TestCase):
    def test_more_than_twenty_tickets_is_allowed_within_raster_budget(self):
        plan = layout((1600,1000), direction='vertical', count=21)
        self.assertEqual(plan['count'],21)
        self.assertEqual(plan['content_px'],[8064,5040])

    def test_exact_width_keeps_aspect_ratio_and_only_pads_last_strip(self):
        plan = layout((1600,1000), direction='vertical', size_mode='width', size_mm=200)
        self.assertEqual(plan['content_px'],[1600,1000])
        self.assertEqual(plan['size_mm'],[200,125])
        self.assertEqual(plan['count'],5)
        self.assertEqual(plan['last_content_mm'],8)
        self.assertEqual(plan['trim_mm'],40)
        self.assertEqual(plan['rows_per_ticket'],1000)

    def test_horizontal_exact_height_rotates_without_changing_content_size(self):
        plan = layout((1600,1000),direction='horizontal',size_mode='height',size_mm=125)
        self.assertEqual(plan['count'],3)
        self.assertEqual(plan['rows_per_ticket'],1600)
        self.assertEqual(plan['trim_mm'],19)

    def test_budget_is_checked_before_allocating_raster(self):
        with self.assertRaises(ValueError):
            layout((100,100),count=10000)

    def test_dimensions_are_rounded_to_a_physical_dot(self):
        plan=layout((100,100),size_mode='width',size_mm=10.03)
        self.assertEqual(plan['size_mm'],[10,10])

    def test_white_padding_remains_white_in_export(self):
        source=Image.new('RGB',(1600,1000),'black')
        plan=layout(source.size,size_mode='width',size_mm=200)
        images=render_strips(source,plan,{'preset':'custom','dither':'none'})
        self.assertEqual(len(images),5)
        self.assertTrue(all(im.size==(384,1000) for im in images))
        self.assertEqual(images[-1].crop((64,0,384,1000)).getextrema(),(255,255))

    def test_presets_and_all_explicit_adjustments_change_the_bitmap(self):
        source=Image.new('RGB',(240,160))
        source.putdata([(x*13%256,y*7%256,(x+y)*11%256) for y in range(160) for x in range(240)])
        plan=layout(source.size,count=1)
        baseline=render_strips(source,plan,{'preset':'custom','dither':'floyd'})[0].tobytes()
        for options in ({'contrast':1.7},{'brightness':1.5},{'sharpness':2},{'strength':1},{'dither':'bayer'},{'preset':'portrait'}):
            self.assertNotEqual(baseline,render_strips(source,plan,{'preset':'custom','dither':'floyd',**options})[0].tobytes(),options)

    def test_preview_is_bounded_for_large_plan(self):
        source=Image.new('RGB',(1600,1000),'gray')
        plan=layout(source.size,count=21)
        image=preview_image(source,plan,{'preset':'custom','dither':'none'})
        self.assertLessEqual(max(image.size),1450)

    def test_horizontal_padding_is_at_left_on_rotated_ticket(self):
        source=Image.new('RGB',(1600,1000),'black')
        plan=layout(source.size,direction='horizontal',size_mode='height',size_mm=125)
        image=render_strips(source,plan,{'dither':'none'})[-1]
        self.assertEqual(image.size,(384,1600))
        self.assertEqual(image.crop((0,0,152,1600)).getextrema(),(255,255))
        self.assertEqual(image.crop((152,0,384,1600)).getextrema(),(0,0))

    def test_each_render_strength_level_has_a_distinct_compensation(self):
        source=Image.linear_gradient('L').resize((240,160)).convert('RGB')
        plan=layout(source.size,count=1)
        outputs=[render_strips(source,plan,{'strength':level})[0].tobytes() for level in range(1,8)]
        self.assertEqual(len(set(outputs)),7)
