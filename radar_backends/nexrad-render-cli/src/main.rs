use anyhow::{anyhow, Result};
use chrono::{Duration, Utc};
use clap::Parser;
use nexrad::model::data::Product;
use nexrad::model::geo::GeoPoint;
use nexrad::process::detection::StormCellDetector;
use nexrad::render::{default_color_scale, render_sweep, RenderOptions, RgbaImage};

#[derive(Parser)]
#[command(name = "nexrad-render-cli", about = "Render NEXRAD images through danielway/nexrad", allow_negative_numbers = true)]
struct Cli {
    #[arg(long)]
    site: Option<String>,

    #[arg(long)]
    lat: Option<f64>,

    #[arg(long)]
    lon: Option<f64>,

    #[arg(long)]
    input: Option<String>,

    #[arg(long, default_value = "ref")]
    product: String,

    #[arg(long, default_value_t = 1024)]
    size: u32,

    #[arg(long, default_value_t = 10.0)]
    min_dbz: f32,

    #[arg(long, default_value_t = 200.0)]
    range_km: f64,

    #[arg(long, default_value_t = false)]
    storm_cells: bool,

    #[arg(short, long)]
    output: Option<String>,
}

fn parse_product(name: &str) -> Result<Product> {
    match name.to_lowercase().as_str() {
        "ref" | "reflectivity" => Ok(Product::Reflectivity),
        "vel" | "velocity" => Ok(Product::Velocity),
        "sw" => Ok(Product::SpectrumWidth),
        "zdr" => Ok(Product::DifferentialReflectivity),
        "rho" | "cc" => Ok(Product::CorrelationCoefficient),
        "phi" | "kdp" => Ok(Product::DifferentialPhase),
        "srv" | "vil" => Err(anyhow!(
            "Product '{}' is not implemented in nexrad-render-cli; use rustdar backend for srv/vil",
            name
        )),
        _ => Err(anyhow!("Unknown product '{}'. Use: ref, vel, sw, zdr, rho, phi", name)),
    }
}

fn blend_pixel(image: &mut RgbaImage, x: i32, y: i32, color: [u8; 4]) {
    if x < 0 || y < 0 {
        return;
    }
    let (w, h) = image.dimensions();
    let x = x as u32;
    let y = y as u32;
    if x >= w || y >= h {
        return;
    }
    let px = image.get_pixel_mut(x, y);
    let alpha = color[3] as f32 / 255.0;
    let inv = 1.0 - alpha;
    px.0[0] = (px.0[0] as f32 * inv + color[0] as f32 * alpha).round() as u8;
    px.0[1] = (px.0[1] as f32 * inv + color[1] as f32 * alpha).round() as u8;
    px.0[2] = (px.0[2] as f32 * inv + color[2] as f32 * alpha).round() as u8;
    px.0[3] = 255;
}

fn draw_ring(image: &mut RgbaImage, cx: i32, cy: i32, radius: i32, color: [u8; 4]) {
    if radius <= 0 {
        return;
    }
    for deg in (0..360).step_by(3) {
        let rad = (deg as f64).to_radians();
        let x = cx + (radius as f64 * rad.cos()).round() as i32;
        let y = cy + (radius as f64 * rad.sin()).round() as i32;
        blend_pixel(image, x, y, color);
    }
}

fn draw_crosshair(image: &mut RgbaImage, cx: i32, cy: i32, radius: i32, color: [u8; 4]) {
    for d in -radius..=radius {
        blend_pixel(image, cx + d, cy, color);
        blend_pixel(image, cx, cy + d, color);
    }
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let product = parse_product(&cli.product)?;

    let site_id = if let Some(site) = &cli.site {
        site.to_uppercase()
    } else if let (Some(lat), Some(lon)) = (cli.lat, cli.lon) {
        nexrad::nearest_site(lat as f32, lon as f32)
            .ok_or_else(|| anyhow!("No radar sites found"))?
            .id
            .to_string()
    } else {
        return Err(anyhow!("Provide --site or both --lat and --lon"));
    };

    let scan = if let Some(input) = &cli.input {
        nexrad::load_file(input)?
    } else {
        let rt = tokio::runtime::Runtime::new()?;
        rt.block_on(async {
            let today = Utc::now().date_naive();
            match nexrad::download_latest(&site_id, today).await {
                Ok(scan) => Ok(scan),
                Err(_) => nexrad::download_latest(&site_id, today - Duration::days(1)).await,
            }
        })?
    };

    let (sweep_idx, field) = nexrad::extract_first_field(&scan, product)
        .ok_or_else(|| anyhow!("No sweep found with product {:?}", product))?;
    let coord = nexrad::coordinate_system_required(&scan)?;
    let options = RenderOptions::new(cli.size as usize, cli.size as usize)
        .with_background([18, 18, 24, 255])
        .with_coord_system(coord.clone())
        .with_extent(coord.sweep_extent(cli.range_km))
        .bilinear();

    let color_scale = default_color_scale(product);
    let result = render_sweep(&field, &color_scale, &options)?;
    let metadata = result.metadata().clone();
    let mut image = result.into_image();
    let mut storm_analysis = None;

    if cli.storm_cells {
        let (_, ref_field) = nexrad::extract_first_field(&scan, Product::Reflectivity)
            .ok_or_else(|| anyhow!("Storm-cell detection requires reflectivity data"))?;
        let detector = StormCellDetector::new(cli.min_dbz.max(20.0), 10)?;
        let cells = detector.detect(&ref_field, &coord)?;

        for cell in &cells {
            let centroid = cell.centroid();
            let point = GeoPoint {
                latitude: centroid.latitude,
                longitude: centroid.longitude,
            };
            if let Some((px, py)) = metadata.geo_to_pixel(&point) {
                draw_ring(&mut image, px.round() as i32, py.round() as i32, 11, [255, 180, 0, 255]);
                draw_crosshair(&mut image, px.round() as i32, py.round() as i32, 6, [255, 180, 0, 255]);
            }
        }

        storm_analysis = Some(serde_json::json!({
            "storm_cell_count": cells.len(),
            "storm_cells": cells.iter().map(|cell| {
                let centroid = cell.centroid();
                serde_json::json!({
                    "id": cell.id(),
                    "centroid": {
                        "lat": centroid.latitude,
                        "lon": centroid.longitude,
                    },
                    "max_reflectivity_dbz": cell.max_reflectivity_dbz(),
                    "mean_reflectivity_dbz": cell.mean_reflectivity_dbz(),
                    "gate_count": cell.gate_count(),
                    "area_km2": cell.area_km2(),
                    "elevation_deg": cell.elevation_degrees(),
                    "max_reflectivity_azimuth_deg": cell.max_reflectivity_azimuth_degrees(),
                    "max_reflectivity_range_km": cell.max_reflectivity_range_km(),
                })
            }).collect::<Vec<_>>(),
        }));
    }

    let output_path = cli
        .output
        .unwrap_or_else(|| format!("radar_{}_{}.png", site_id, cli.product));
    image.save(&output_path)?;

    let site_meta = scan.site();
    let timestamp = scan
        .time_range()
        .map(|(_, latest)| latest.to_rfc3339());
    let json = serde_json::json!({
        "image_path": output_path,
        "site": site_meta.map(|s| s.identifier_string()).unwrap_or(site_id.clone()),
        "site_name": site_meta.map(|s| s.identifier_string()).unwrap_or(site_id.clone()),
        "product": cli.product,
        "range_km": cli.range_km,
        "image_size": cli.size,
        "elevation_deg": field.elevation_degrees(),
        "timestamp": timestamp,
        "input_path": cli.input,
        "storm_cells": cli.storm_cells,
        "storm_analysis": storm_analysis,
        "backend": "nexrad",
    });
    println!("{}", json);

    Ok(())
}
