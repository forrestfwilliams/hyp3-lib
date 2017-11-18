#!/usr/bin/python

import argparse
from argparse import RawTextHelpFormatter
import os
import sys
import lxml.etree as et
from osgeo import gdal, ogr, osr
from osgeo.gdalconst import *
import zipfile


def resample_geotiff(geotiff, width, outFormat, outFile):

  # Suppress GDAL warnings
  gdal.UseExceptions()
  gdal.PushErrorHandler('CPLQuietErrorHandler')

  # Extract information from GeoTIFF
  raster = gdal.Open(geotiff)
  bandCount = raster.RasterCount

  if outFormat.upper() == 'GEOTIFF':
    gdal.Translate(outFile, raster, resampleArg=GRIORA_Cubic, width=width)
  elif outFormat.upper() == 'JPEG' or outFormat.upper() == 'JPG':
    gdal.Translate(outFile, raster, format='JPEG', resampleAlg=GRIORA_Cubic,
      width=width)
  elif outFormat.upper() == 'PNG':
    if bandCount == 1:
      gdal.Translate(outFile, raster, format='PNG', resampleAlg=GRIORA_Cubic,
        width=width, noData='0')
    elif bandCount == 3:
      gdal.Translate(outFile, raster, format='PNG', resampleAlg=GRIORA_Cubic,
        width=width, noData='0 0 0')
  elif outFormat.upper() == 'KML':

    # Reproject to geographic coordinates first
    orgExt = os.path.splitext(outFile)[1]
    tmpExt = ('_{0}.tif'.format(os.getpid()))
    tmpFile = outFile.replace(orgExt, tmpExt)
    if bandCount == 1:
      gdal.Warp(tmpFile, raster, resampleAlg=GRIORA_Cubic, width=width,
        srcNodata='0', dstSRS='EPSG:4326', dstAlpha=True)
    elif bandCount == 3:
      gdal.Warp(tmpFile, raster, resampleAlg=GRIORA_Cubic, width=width,
        srcNodata='0 0 0', dstSRS='EPSG:4326', dstAlpha=True)
    raster = None

    # Convert GeoTIFF to PNG - since warp cannot do that in one step
    raster = gdal.Open(tmpFile)
    pngFile = outFile.replace(orgExt, '.png')
    gdal.Translate(pngFile, raster, format='PNG', resampleAlg=GRIORA_Cubic)

    # Extract metadata from GeoTIFF to fill into the KML
    gt = raster.GetGeoTransform()
    coordStr = ('%.4f,%.4f %.4f,%.4f %.4f,%.4f %.4f,%.4f' %
      (gt[0], gt[3]+raster.RasterYSize*gt[5], gt[0]+raster.RasterXSize*gt[1],
        gt[3]+raster.RasterYSize*gt[5], gt[0]+raster.RasterXSize*gt[1], gt[3],
        gt[0], gt[3]))

    # Take care of namespaces
    prefix = {}
    gx = '{http://www.google.com/kml/ext/2.2}'
    prefix['gx'] = gx
    ns_gx = {'gx' : 'http://www.google.com/kml/ext/2.2'}
    ns_main = { None : 'http://www.opengis.net/kml/2.2'}
    ns = dict(list(ns_main.items()) + list(ns_gx.items()))

    # Fill in the tree structure
    kmlFile = outFile.replace(orgExt, '.kml')
    kml = et.Element('kml', nsmap=ns)
    overlay = et.SubElement(kml, 'GroundOverlay')
    et.SubElement(overlay, 'name').text = \
      geotiff.replace('.tif', '') + ' overlay'
    icon = et.SubElement(overlay, 'Icon')
    et.SubElement(icon, 'href').text = pngFile
    et.SubElement(icon, 'viewBoundScale').text = '0.75'
    latLonQuad = et.SubElement(overlay, '{0}LatLonQuad'.format(gx))
    et.SubElement(latLonQuad, 'coordinates').text = coordStr
    with open(kmlFile, 'w') as outF:
      outF.write(et.tostring(kml, xml_declaration=True, encoding='utf-8',
        pretty_print=True))
    outF.close()

    # Zip PNG and KML together
    zipFile = outFile.replace(orgExt, '.kmz')
    zip = zipfile.ZipFile(zipFile, 'w', zipfile.ZIP_DEFLATED)
    zip.write(kmlFile)
    zip.write(pngFile)
    zip.close()

    # Clean up - remove temporary GeoTIFF, KML and PNG
    os.remove(tmpFile)
    os.remove(pngFile)
    os.remove(pngFile + '.aux.xml')
    os.remove(kmlFile)


if __name__ == '__main__':

  parser = argparse.ArgumentParser(prog='resample_geotiff',
    description='Resamples a GeoTIFF file and saves it in a number of formats',
    formatter_class=RawTextHelpFormatter)
  parser.add_argument('geotiff', help='name of GeoTIFF file (input)')
  parser.add_argument('width', help='target width (input)')
  parser.add_argument('format', help='output format: GeoTIFF, JPEG, PNG, KML')
  parser.add_argument('output', help='name of output file (output)')
  if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)
  args = parser.parse_args()

  if not os.path.exists(args.geotiff):
    print('GeoTIFF file (%s) does not exist!' % args.geotiff)
    sys.exit(1)
  if len(os.path.splitext(args.output)[1]) == 0:
    print('Output file (%s) does not have an extension!' % args.output)
    sys.exit(1)

  resample_geotiff(args.geotiff, args.width, args.format, args.output)
