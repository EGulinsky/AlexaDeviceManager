cask "alexa-device-manager" do
  version "2.0.0"
  sha256 ""

  url "https://github.com/your-username/alexa-device-manager/releases/download/v#{version}/Alexa-Device-Manager-#{version}.dmg"
  name "Alexa Device Manager"
  desc "Cross-platform desktop app for managing Amazon Alexa smart home devices"
  homepage "https://github.com/your-username/alexa-device-manager"

  livecheck do
    url :url
    strategy :github_latest
  end

  app "Alexa Device Manager.app"
end
