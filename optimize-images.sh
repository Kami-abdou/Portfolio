#!/bin/bash
set -e
cd "/Users/abdallahyaackoubi/Documents/Claude Projects/Portfolio/Portfolio"
SRC="UX UI Design Portfolio"
mkdir -p assets/thumbs assets/projects/steer assets/projects/groupado assets/projects/konnect assets/projects/fissa3 assets/projects/fixerloop assets/projects/undrive assets/projects/pharmadrive

# helper: resize+convert to jpeg. $1=src $2=out $3=width $4=quality
mk() {
  sips -s format jpeg -s formatOptions "${4:-85}" --resampleWidth "$3" "$1" --out "$2" >/dev/null 2>&1 && echo "  ✓ $2"
}

echo "== Thumbnails (900w) =="
mk "$SRC/Case Studies/Steer/design_process.png"            assets/thumbs/steer.jpg       900
mk "$SRC/Case Studies/Groupado/Screenshot_2023-10-30_at_2.46.25_PM.png" assets/thumbs/groupado.jpg 900
mk "$SRC/Case Studies/Konnect/ux_process.png"              assets/thumbs/konnect.jpg     900
mk "$SRC/Case Studies/Fissa3/user_funding.png"             assets/thumbs/fissa3.jpg      900
mk "$SRC/Other Projects I’m proud of/Fixerloop/Screenshot_2023-10-30_at_3.09.57_PM.png" assets/thumbs/fixerloop.jpg 900
mk "$SRC/Other Projects I’m proud of/UnDrive Website/Undrive_homepage.png" assets/thumbs/undrive.jpg 900
mk "$SRC/Other Projects I’m proud of/PharmaDrive/onboarding.png" assets/thumbs/pharmadrive.jpg 900

echo "== Steer =="
mk "$SRC/Case Studies/Steer/design_process.png" assets/projects/steer/design-process.jpg 1200
mk "$SRC/Case Studies/Steer/answers.png"        assets/projects/steer/answers.jpg        1200
mk "$SRC/Case Studies/Steer/analysis.png"       assets/projects/steer/analysis.jpg       1200
mk "$SRC/Case Studies/Steer/User_persona.png"   assets/projects/steer/user-persona.jpg   1200
mk "$SRC/Case Studies/Steer/user_journey.png"   assets/projects/steer/user-journey.jpg   1200
mk "$SRC/Case Studies/Steer/user_flow.png"      assets/projects/steer/user-flow.jpg      1200

echo "== Konnect =="
mk "$SRC/Case Studies/Konnect/ux_process.png"               assets/projects/konnect/ux-process.jpg            1200
mk "$SRC/Case Studies/Konnect/understanding_the_problem.png" assets/projects/konnect/understanding-problem.jpg 1200
mk "$SRC/Case Studies/Konnect/validate_the_design.png"      assets/projects/konnect/validate-design.jpg       1200

echo "== Fissa3 =="
mk "$SRC/Case Studies/Fissa3/user_funding.png"   assets/projects/fissa3/user-funding.jpg   1200
mk "$SRC/Case Studies/Fissa3/User_personas.png"  assets/projects/fissa3/user-personas.jpg  1200
mk "$SRC/Case Studies/Fissa3/emapthy_mapping.png" assets/projects/fissa3/empathy-mapping.jpg 1200
mk "$SRC/Case Studies/Fissa3/taskflow.png"       assets/projects/fissa3/taskflow.jpg       1200
mk "$SRC/Case Studies/Fissa3/sketching.png"      assets/projects/fissa3/sketching.jpg      1200
mk "$SRC/Case Studies/Fissa3/wireframes.png"     assets/projects/fissa3/wireframes.jpg     1200
mk "$SRC/Case Studies/Fissa3/HI-fi.png"          assets/projects/fissa3/hi-fi.jpg          1200

echo "== Groupado =="
mk "$SRC/Case Studies/Groupado/Homepagenotion.png"                  assets/projects/groupado/homepage.jpg  1200
mk "$SRC/Case Studies/Groupado/Screenshot_2023-10-30_at_2.46.25_PM.png" assets/projects/groupado/screen-1.jpg 1200
mk "$SRC/Case Studies/Groupado/Screenshot_2023-10-30_at_2.46.39_PM.png" assets/projects/groupado/screen-2.jpg 1200

echo "== Fixerloop =="
mk "$SRC/Other Projects I’m proud of/Fixerloop/Screenshot_2023-10-30_at_3.09.57_PM.png" assets/projects/fixerloop/screen-1.jpg 1200
mk "$SRC/Other Projects I’m proud of/Fixerloop/Screenshot_2023-10-30_at_3.10.09_PM.png" assets/projects/fixerloop/screen-2.jpg 1200
mk "$SRC/Other Projects I’m proud of/Fixerloop/Screenshot_2023-10-30_at_3.10.18_PM.png" assets/projects/fixerloop/screen-3.jpg 1200

echo "== UnDrive =="
mk "$SRC/Other Projects I’m proud of/UnDrive Website/Undrive_homepage.png" assets/projects/undrive/homepage.jpg 1200
mk "$SRC/Other Projects I’m proud of/UnDrive Website/autoecole_page.png"   assets/projects/undrive/autoecole.jpg 1200
mk "$SRC/Other Projects I’m proud of/UnDrive Website/Listing_proposition_2_nb_recherche.png" assets/projects/undrive/listing.jpg 1200

echo "== PharmaDrive =="
mk "$SRC/Other Projects I’m proud of/PharmaDrive/onboarding.png"   assets/projects/pharmadrive/onboarding.jpg 1200
mk "$SRC/Other Projects I’m proud of/PharmaDrive/pharmadrive2.png" assets/projects/pharmadrive/screen-2.jpg   1200
mk "$SRC/Other Projects I’m proud of/PharmaDrive/3.png"            assets/projects/pharmadrive/screen-3.jpg   1200

echo "== Done. Sizes: =="
du -sh assets/thumbs assets/projects/*
